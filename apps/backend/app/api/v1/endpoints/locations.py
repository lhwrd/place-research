"""Custom locations endpoints for managing family/friends addresses."""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.exceptions import NotFoundError, PropertyNotFoundError
from app.models.user import User
from app.schemas.custom_location import (
    CustomLocationCreate,
    CustomLocationList,
    CustomLocationResponse,
    CustomLocationUpdate,
    CustomLocationWithDistance,
    LocationTypeEnum,
)
from app.services.custom_location_service import CustomLocationService
from app.services.distance_service import DistanceService
from app.services.geocoding_service import GeocodingService
from app.services.property_service import PropertyService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=CustomLocationList,
    summary="Get all custom locations",
    description="Get all custom locations (family/friends addresses) for the current user",
)
async def get_custom_locations(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    location_type: Optional[LocationTypeEnum] = Query(None, description="Filter by location type"),
    sort_by: str = Query("priority", description="Sort field (priority, name, created_at)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all custom locations for the current user.

    Custom locations are used to calculate distances from properties to
    important places like family homes, friends' apartments, etc.

    Supports filtering by:
    - Active status
    - Location type (family, friend, work, other)

    Supports sorting by:
    - priority (higher priority locations are shown first)
    - name (alphabetical)
    - created_at (most recent first)
    """
    location_service = CustomLocationService(db)

    locations, total = location_service.get_user_locations(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        location_type=location_type.value if location_type else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return CustomLocationList(
        items=[CustomLocationResponse.model_validate(loc) for loc in locations],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=CustomLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom location",
    description="Add a new custom location (family/friend address)",
)
async def create_custom_location(
    location_data: CustomLocationCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new custom location.

    Provide either:
    - **address**: Will be automatically geocoded
    - **latitude & longitude**: Direct coordinates

    Required:
    - **name**:  Friendly name (e.g., "Mom's House", "Best Friend's Apt")

    Optional:
    - **description**: Additional details
    - **location_type**: Category (family, friend, work, other)
    - **priority**: Display priority (higher = more important)
    """
    location_service = CustomLocationService(db)
    geocoding_service = GeocodingService()

    # Prepare location data (include defaults for fields like location_type)
    location_dict = location_data.dict()

    # If address provided, geocode it
    if location_data.address:
        try:
            geocode_result = await geocoding_service.geocode_address(location_data.address)

            location_dict["address"] = geocode_result["formatted_address"]
            location_dict["latitude"] = geocode_result["latitude"]
            location_dict["longitude"] = geocode_result["longitude"]
            location_dict["city"] = geocode_result.get("city")
            location_dict["state"] = geocode_result.get("state")
            location_dict["zip_code"] = geocode_result.get("zip_code")

        except Exception as e:
            logger.error(f"Failed to geocode address: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not geocode address. Please check and try again.",
            ) from e

    # If coordinates provided directly
    elif location_data.latitude is not None and location_data.longitude is not None:
        location_dict["latitude"] = location_data.latitude
        location_dict["longitude"] = location_data.longitude

        # Optionally reverse geocode to get address
        if not location_data.address:
            try:
                reverse_result = await geocoding_service.reverse_geocode(
                    location_data.latitude, location_data.longitude
                )
                if reverse_result:
                    location_dict["address"] = reverse_result["formatted_address"]
                    location_dict["city"] = reverse_result.get("city")
                    location_dict["state"] = reverse_result.get("state")
                    location_dict["zip_code"] = reverse_result.get("zip_code")
            except (HTTPException, ValueError, KeyError) as e:
                logger.debug(f"Reverse geocoding failed (non-critical): {e}")
                # Non-critical, continue without address

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either address or latitude/longitude",
        )

    # Validate coordinates are present
    if "latitude" not in location_dict or "longitude" not in location_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to obtain coordinates for location",
        )

    # Create location
    custom_location = location_service.create_location(
        user_id=current_user.id, location_data=location_dict
    )

    logger.info("User %s created custom location: %s", current_user.id, custom_location.name)

    return CustomLocationResponse.model_validate(custom_location)


@router.get(
    "/{location_id}",
    response_model=CustomLocationResponse,
    summary="Get custom location by ID",
    description="Get details of a specific custom location",
)
async def get_custom_location(
    location_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific custom location by ID.
    """
    location_service = CustomLocationService(db)

    custom_location = location_service.get_location_by_id(
        location_id=location_id, user_id=current_user.id
    )

    if not custom_location:
        raise NotFoundError(f"Custom location {location_id} not found")

    return CustomLocationResponse.model_validate(custom_location)


@router.put(
    "/{location_id}",
    response_model=CustomLocationResponse,
    summary="Update custom location",
    description="Update a custom location's details",
)
async def update_custom_location(
    location_id: int,
    update_data: CustomLocationUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a custom location.

    You can update:
    - name
    - description
    - address (will be re-geocoded)
    - coordinates (latitude/longitude)
    - location_type
    - priority
    - is_active
    """
    location_service = CustomLocationService(db)
    geocoding_service = GeocodingService()

    updates = update_data.dict(exclude_unset=True)

    # If address is being updated, re-geocode
    if "address" in updates and updates["address"]:
        try:
            geocode_result = await geocoding_service.geocode_address(updates["address"])

            updates["address"] = geocode_result["formatted_address"]
            updates["latitude"] = geocode_result["latitude"]
            updates["longitude"] = geocode_result["longitude"]
            updates["city"] = geocode_result.get("city")
            updates["state"] = geocode_result.get("state")
            updates["zip_code"] = geocode_result.get("zip_code")

        except Exception as e:
            logger.error(f"Failed to geocode address: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not geocode address. Please check and try again.",
            ) from e

    # If coordinates are being updated without address, reverse geocode
    elif "latitude" in updates and "longitude" in updates:
        try:
            reverse_result = await geocoding_service.reverse_geocode(
                updates["latitude"], updates["longitude"]
            )
            if reverse_result:
                updates["address"] = reverse_result["formatted_address"]
                updates["city"] = reverse_result.get("city")
                updates["state"] = reverse_result.get("state")
                updates["zip_code"] = reverse_result.get("zip_code")
        except (HTTPException, ValueError, KeyError):
            pass  # Non-critical

    custom_location = location_service.update_location(
        location_id=location_id, user_id=current_user.id, updates=updates
    )

    if not custom_location:
        raise NotFoundError(f"Custom location {location_id} not found")

    logger.info(f"User {current_user.id} updated custom location {location_id}")

    return CustomLocationResponse.model_validate(custom_location)


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete custom location",
    description="Delete a custom location",
)
async def delete_custom_location(
    location_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a custom location.

    This permanently removes the location.  Properties will no longer show
    distances to this location in future enrichments.
    """
    location_service = CustomLocationService(db)

    deleted = location_service.delete_location(location_id=location_id, user_id=current_user.id)

    if not deleted:
        raise NotFoundError(f"Custom location {location_id} not found")

    logger.info(f"User {current_user.id} deleted custom location {location_id}")

    return None


@router.patch(
    "/{location_id}/activate",
    response_model=CustomLocationResponse,
    summary="Activate/deactivate location",
    description="Toggle active status for a custom location",
)
async def toggle_location_active(
    location_id: int,
    is_active: bool = Query(..., description="Set active status"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Activate or deactivate a custom location.

    Inactive locations are not used in distance calculations but are not deleted.
    This is useful for temporarily excluding a location without losing it.
    """
    location_service = CustomLocationService(db)

    custom_location = location_service.update_location(
        location_id=location_id,
        user_id=current_user.id,
        updates={"is_active": is_active},
    )

    if not custom_location:
        raise NotFoundError(f"Custom location {location_id} not found")

    return CustomLocationResponse.model_validate(custom_location)


@router.patch(
    "/{location_id}/priority",
    response_model=CustomLocationResponse,
    summary="Update priority",
    description="Update the priority/importance of a custom location",
)
async def update_location_priority(
    location_id: int,
    priority: int = Query(
        ..., ge=0, le=100, description="Priority (0-100, higher is more important)"
    ),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update location priority.

    Priority determines the order locations are displayed and can indicate
    which distances are most important to you.

    - 100:  Highest priority (e.g., daily commute)
    - 50: Medium priority (e.g., visit weekly)
    - 0: Low priority (e.g., visit occasionally)
    """
    location_service = CustomLocationService(db)

    custom_location = location_service.update_location(
        location_id=location_id, user_id=current_user.id, updates={"priority": priority}
    )

    if not custom_location:
        raise NotFoundError(f"Custom location {location_id} not found")

    return CustomLocationResponse.model_validate(custom_location)


@router.get(
    "/active/list",
    response_model=CustomLocationList,
    summary="Get active locations",
    description="Get only active custom locations",
)
async def get_active_locations(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get all active custom locations.

    These are the locations that will be used in property enrichment
    distance calculations.
    """
    location_service = CustomLocationService(db)

    locations, total = location_service.get_user_locations(
        user_id=current_user.id, is_active=True, sort_by="priority", sort_order="desc"
    )

    return CustomLocationList(
        items=[CustomLocationResponse.model_validate(loc) for loc in locations],
        total=total,
        skip=0,
        limit=total,
    )


@router.get(
    "/types/list",
    summary="Get locations by type",
    description="Get locations grouped by type",
)
async def get_locations_by_type(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get custom locations grouped by type.

    Returns locations organized by category:
    - family
    - friend
    - work
    - other
    """
    location_service = CustomLocationService(db)

    grouped_locations = location_service.get_locations_by_type(current_user.id)

    return grouped_locations


@router.get(
    "/distance-from/{location_id}",
    summary="Calculate distance from location",
    description="Calculate distance from a custom location to an address",
)
async def calculate_distance_from_location(
    location_id: int,
    address: str = Query(..., description="Destination address"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Calculate distance and travel time from a custom location to an address.

    Useful for checking how far a potential property is from a specific location
    before saving/searching for it.
    """
    location_service = CustomLocationService(db)
    geocoding_service = GeocodingService()

    # Get custom location
    custom_location = location_service.get_location_by_id(
        location_id=location_id, user_id=current_user.id
    )

    if not custom_location:
        raise NotFoundError(f"Custom location {location_id} not found")

    # Geocode destination address
    try:
        destination = await geocoding_service.geocode_address(address)
    except Exception as e:
        logger.error(f"Failed to geocode address:  {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not geocode destination address",
        ) from e

    # Calculate distance

    distance_service = DistanceService()

    try:
        distances = await distance_service.calculate_distances(
            origin_lat=custom_location["latitude"],
            origin_lon=custom_location["longitude"],
            destinations=[(destination["latitude"], destination["longitude"])],
        )

        if distances:
            result = distances[0]
            return {
                "from_location": custom_location["name"],
                "from_address": custom_location["address"],
                "to_address": destination["formatted_address"],
                "distance_miles": result.get("distance_miles"),
                "driving_time_minutes": result.get("driving_time_minutes"),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to calculate distance",
            )

    except Exception as e:
        logger.error(f"Distance calculation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate distance",
        ) from e


@router.get(
    "/distances-to-property/{property_id}",
    response_model=List[CustomLocationWithDistance],
    summary="Get distances to property",
    description="Get all custom location distances to a specific property",
)
async def get_distances_to_property(
    property_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get distances from all active custom locations to a property.

    This shows you how far the property is from all your important locations.
    """
    location_service = CustomLocationService(db)

    # Get property
    property_service = PropertyService(db)

    property_data = await property_service.get_property_by_id(
        property_id=property_id, user_id=current_user.id
    )

    if not property_data:
        raise PropertyNotFoundError(property_id=property_id)

    # Get active locations
    locations, _ = location_service.get_user_locations(user_id=current_user.id, is_active=True)

    if not locations:
        return []

    # Calculate distances
    distance_service = DistanceService()

    destinations = [(loc["latitude"], loc["longitude"]) for loc in locations]

    try:
        distances = await distance_service.calculate_distances(
            origin_lat=property_data.latitude,
            origin_lon=property_data.longitude,
            destinations=destinations,
        )

        # Combine location data with distance data
        result = []
        distance_map = {d["location_id"]: d for d in distances}

        for loc in locations:
            distance_info = distance_map.get(loc["id"], {})
            result.append(
                CustomLocationWithDistance(
                    distance_miles=distance_info.get("distance_miles"),
                    driving_time_minutes=distance_info.get("driving_time_minutes"),
                    **CustomLocationResponse.model_validate(loc).model_dump(),
                )
            )

        # Sort by distance
        result.sort(key=lambda x: x.distance_miles or float("inf"))

        return result

    except Exception as e:
        logger.error(f"Distance calculation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate distances",
        ) from e


@router.get(
    "/stats/summary",
    summary="Get location statistics",
    description="Get statistics about custom locations",
)
async def get_location_stats(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get statistics about your custom locations.

    Returns:
    - Total locations
    - Active locations
    - Locations by type
    - Most recently added
    """
    location_service = CustomLocationService(db)
    stats = location_service.get_user_stats(current_user.id)

    return stats


@router.post(
    "/bulk/activate",
    summary="Bulk activate locations",
    description="Activate multiple locations at once",
)
async def bulk_activate_locations(
    location_ids: List[int],
    is_active: bool = Query(..., description="Set active status"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Activate or deactivate multiple locations at once.
    """
    location_service = CustomLocationService(db)

    updated_count = location_service.bulk_update(
        user_id=current_user.id,
        location_ids=location_ids,
        updates={"is_active": is_active},
    )

    return {"message": f"Updated {updated_count} locations", "count": updated_count}


@router.post(
    "/bulk/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bulk delete locations",
    description="Delete multiple locations at once",
)
async def bulk_delete_locations(
    location_ids: List[int],
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete multiple custom locations at once.
    """
    location_service = CustomLocationService(db)

    deleted_count = location_service.bulk_delete(user_id=current_user.id, location_ids=location_ids)

    logger.info(f"User {current_user.id} bulk deleted {deleted_count} locations")

    return None


@router.post(
    "/import",
    response_model=List[CustomLocationResponse],
    summary="Import multiple locations",
    description="Import multiple custom locations at once",
)
async def import_locations(
    locations: List[CustomLocationCreate],
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Import multiple custom locations at once.

    Useful for bulk setup or migrating from another system.
    Each location will be geocoded if only address is provided.
    """
    location_service = CustomLocationService(db)
    geocoding_service = GeocodingService()

    created_locations = []
    errors = []

    for idx, location_data in enumerate(locations):
        try:
            location_dict = location_data.dict(exclude_unset=True)

            # Geocode if needed
            if location_data.address and not location_data.latitude:
                try:
                    geocode_result = await geocoding_service.geocode_address(location_data.address)
                    location_dict.update(
                        {
                            "address": geocode_result["formatted_address"],
                            "latitude": geocode_result["latitude"],
                            "longitude": geocode_result["longitude"],
                            "city": geocode_result.get("city"),
                            "state": geocode_result.get("state"),
                            "zip_code": geocode_result.get("zip_code"),
                        }
                    )
                except (HTTPException, ValueError, KeyError) as e:
                    errors.append(
                        {
                            "index": idx,
                            "name": location_data.name,
                            "error": f"Geocoding failed:  {str(e)}",
                        }
                    )
                    continue

            # Create location
            custom_location = location_service.create_location(
                user_id=current_user.id, location_data=location_dict
            )
            created_locations.append(custom_location)

        except (HTTPException, ValueError, KeyError) as e:
            errors.append({"index": idx, "name": location_data.name, "error": str(e)})

    logger.info(
        f"User {current_user.id} imported {len(created_locations)} locations "
        f"({len(errors)} errors)"
    )

    if errors:
        return {
            "created": [CustomLocationResponse.model_validate(loc) for loc in created_locations],
            "errors": errors,
            "message": f"Imported {len(created_locations)} locations with {len(errors)} errors",
        }

    return [CustomLocationResponse.model_validate(loc) for loc in created_locations]
