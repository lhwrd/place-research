"""User preferences endpoints for customizing property enrichment."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.models.user import User
from app.schemas.user_preference import (
    AmenityPreferencesUpdate,
    PropertyCriteriaUpdate,
    UserPreferenceCreate,
    UserPreferenceResponse,
    UserPreferenceUpdate,
)
from app.services.user_preference_service import UserPreferenceService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=UserPreferenceResponse,
    summary="Get user preferences",
    description="Get the current user's enrichment preferences",
)
async def get_preferences(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get current user's preferences.

    Returns all preference settings including:
    - Walkability thresholds
    - Distance limits for amenities
    - Property criteria
    - Workplace location
    - Preferred amenity types
    """
    preference_service = UserPreferenceService(db)
    preferences = preference_service.get_or_create_preferences(current_user.id)

    return UserPreferenceResponse.from_orm(preferences)


@router.post(
    "",
    response_model=UserPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user preferences",
    description="Create initial preferences for the user",
)
async def create_preferences(
    preference_data: UserPreferenceCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create user preferences.

    This is typically called automatically when a user registers,
    but can be used to reset preferences to specific values.
    """
    preference_service = UserPreferenceService(db)

    # Check if preferences already exist
    existing = preference_service.get_preferences(current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preferences already exist.  Use PUT to update.",
        )

    preferences = preference_service.create_preferences(
        user_id=current_user.id,
        preference_data=preference_data.dict(exclude_unset=True),
    )

    logger.info(f"Created preferences for user {current_user.id}")

    return UserPreferenceResponse.from_orm(preferences)


@router.put(
    "",
    response_model=UserPreferenceResponse,
    summary="Update user preferences",
    description="Update the current user's preferences (full update)",
)
async def update_preferences(
    preference_data: UserPreferenceUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update user preferences.

    Performs a full update of preferences.  Only provided fields will be updated.
    """
    preference_service = UserPreferenceService(db)

    preferences = preference_service.update_preferences(
        user_id=current_user.id, updates=preference_data.dict(exclude_unset=True)
    )

    logger.info(f"Updated preferences for user {current_user.id}")

    return UserPreferenceResponse.from_orm(preferences)


@router.patch(
    "/walkability",
    response_model=UserPreferenceResponse,
    summary="Update walkability preferences",
    description="Update minimum walk/bike/transit score thresholds",
)
async def update_walkability_preferences(
    min_walk_score: Optional[int] = None,
    min_bike_score: Optional[int] = None,
    min_transit_score: Optional[int] = None,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update walkability score thresholds.

    Set minimum acceptable scores for walk, bike, and transit scores.
    Scores range from 0-100. Common thresholds:
    - 90-100: Walker's Paradise / Very Bikeable
    - 70-89: Very Walkable / Bikeable
    - 50-69: Somewhat Walkable / Bikeable
    - 25-49: Car-Dependent
    - 0-24: Very Car-Dependent
    """
    preference_service = UserPreferenceService(db)

    updates = {}
    if min_walk_score is not None:
        if not 0 <= min_walk_score <= 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Walk score must be between 0 and 100",
            )
        updates["min_walk_score"] = min_walk_score

    if min_bike_score is not None:
        if not 0 <= min_bike_score <= 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bike score must be between 0 and 100",
            )
        updates["min_bike_score"] = min_bike_score

    if min_transit_score is not None:
        if not 0 <= min_transit_score <= 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transit score must be between 0 and 100",
            )
        updates["min_transit_score"] = min_transit_score

    preferences = preference_service.update_preferences(current_user.id, updates)

    return UserPreferenceResponse.from_orm(preferences)


@router.patch(
    "/amenity-distances",
    response_model=UserPreferenceResponse,
    summary="Update amenity distance limits",
    description="Update maximum acceptable distances to various amenities",
)
async def update_amenity_distances(
    amenity_prefs: AmenityPreferencesUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update maximum distances to amenities.

    Set how far away amenities can be (in miles) and still be acceptable.

    Examples:
    - max_grocery_distance: 2. 0 (prefer grocery within 2 miles)
    - max_park_distance: 1.0 (prefer parks within 1 mile)
    - max_school_distance: 3.0 (prefer schools within 3 miles)
    """
    preference_service = UserPreferenceService(db)

    updates = amenity_prefs.dict(exclude_unset=True)

    # Validate distances are positive
    for key, value in updates.items():
        if value is not None and value < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{key} must be a positive number",
            )

    preferences = preference_service.update_preferences(current_user.id, updates)

    return UserPreferenceResponse.from_orm(preferences)


@router.patch(
    "/property-criteria",
    response_model=UserPreferenceResponse,
    summary="Update property criteria",
    description="Update minimum property requirements (bedrooms, bathrooms, etc.)",
)
async def update_property_criteria(
    criteria: PropertyCriteriaUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update property search criteria.

    Set minimum requirements for properties:
    - Bedrooms
    - Bathrooms
    - Square footage
    - Year built (minimum)
    - Property types
    - Price range
    """
    preference_service = UserPreferenceService(db)

    updates = criteria.dict(exclude_unset=True)
    preferences = preference_service.update_preferences(current_user.id, updates)

    return UserPreferenceResponse.from_orm(preferences)


@router.put(
    "/preferred-amenities",
    response_model=UserPreferenceResponse,
    summary="Set preferred amenities",
    description="Set the list of amenity types you care about",
)
async def set_preferred_amenities(
    amenities: list[str],
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Set preferred amenity types.

    Provide a list of amenity types you want to see in property enrichment.

    Available types:
    - grocery_store, supermarket
    - park, playground
    - restaurant, cafe, coffee_shop
    - school, university
    - hospital, pharmacy, doctor
    - gym, fitness_center
    - library
    - shopping_mall, store
    - movie_theater, entertainment
    - public_transit, bus_station, subway_station
    """
    preference_service = UserPreferenceService(db)

    # Validate amenity types (optional - you could have a whitelist)
    valid_amenities = {
        "grocery_store",
        "supermarket",
        "park",
        "playground",
        "restaurant",
        "cafe",
        "coffee_shop",
        "school",
        "university",
        "hospital",
        "pharmacy",
        "doctor",
        "gym",
        "fitness_center",
        "library",
        "shopping_mall",
        "store",
        "movie_theater",
        "entertainment",
        "public_transit",
        "bus_station",
        "subway_station",
    }

    invalid = [a for a in amenities if a not in valid_amenities]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid amenity types: {', '.join(invalid)}",
        )

    updates = {"preferred_amenities": amenities}
    preferences = preference_service.update_preferences(current_user.id, updates)

    return UserPreferenceResponse.from_orm(preferences)


@router.put(
    "/preferred-places",
    response_model=UserPreferenceResponse,
    summary="Set preferred places",
    description="Set the list of place names you care about",
)
async def set_preferred_places(
    places: list[str],
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Set preferred place names.

    Provide a list of place names you want to see in property enrichment.
    """
    preference_service = UserPreferenceService(db)

    updates = {"preferred_places": places}
    preferences = preference_service.update_preferences(current_user.id, updates)

    return UserPreferenceResponse.from_orm(preferences)


@router.patch(
    "/notifications",
    response_model=UserPreferenceResponse,
    summary="Update notification preferences",
    description="Enable/disable various notification types",
)
async def update_notification_preferences(
    notify_new_listings: Optional[bool] = None,
    notify_price_changes: Optional[bool] = None,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update notification preferences.

    Control which types of notifications you want to receive:
    - notify_new_listings: Get notified when new properties match your criteria
    - notify_price_changes: Get notified when saved property prices change
    """
    preference_service = UserPreferenceService(db)

    updates = {}
    if notify_new_listings is not None:
        updates["notify_new_listings"] = notify_new_listings
    if notify_price_changes is not None:
        updates["notify_price_changes"] = notify_price_changes

    preferences = preference_service.update_preferences(current_user.id, updates)

    return UserPreferenceResponse.from_orm(preferences)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset preferences to defaults",
    description="Reset all preferences to default values",
)
async def reset_preferences(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> None:
    """
    Reset preferences to defaults.

    This will clear all custom preferences and restore default values.
    """
    preference_service = UserPreferenceService(db)
    preference_service.reset_to_defaults(current_user.id)

    logger.info(f"Reset preferences to defaults for user {current_user. id}")

    return None


@router.get(
    "/summary",
    summary="Get preferences summary",
    description="Get a human-readable summary of preferences",
)
async def get_preferences_summary(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get a human-readable summary of your preferences.

    Returns a formatted summary of all your preference settings.
    """
    preference_service = UserPreferenceService(db)
    preferences = preference_service.get_or_create_preferences(current_user.id)

    summary = {
        "walkability": {
            "minimum_walk_score": preferences.min_walk_score or "Not set",
            "minimum_bike_score": preferences.min_bike_score or "Not set",
            "minimum_transit_score": preferences.min_transit_score or "Not set",
        },
        "amenity_distances": {
            "grocery_stores": (
                f"Within {preferences.max_grocery_distance} miles"
                if preferences.max_grocery_distance
                else "Not set"
            ),
            "parks": (
                f"Within {preferences.max_park_distance} miles"
                if preferences.max_park_distance
                else "Not set"
            ),
            "schools": (
                f"Within {preferences.max_school_distance} miles"
                if preferences.max_school_distance
                else "Not set"
            ),
            "hospitals": (
                f"Within {preferences.max_hospital_distance} miles"
                if preferences.max_hospital_distance
                else "Not set"
            ),
        },
        "property_criteria": {
            "minimum_bedrooms": preferences.min_bedrooms or "Not set",
            "minimum_bathrooms": preferences.min_bathrooms or "Not set",
            "minimum_square_feet": preferences.min_square_feet or "Not set",
            "price_range": (
                f"${preferences.min_price:,} - ${preferences.max_price:,}"
                if preferences.min_price and preferences.max_price
                else "Not set"
            ),
        },
        "workplace": {
            "address": preferences.workplace_address or "Not set",
            "max_commute_time": (
                f"{preferences.max_commute_time} minutes"
                if preferences.max_commute_time
                else "Not set"
            ),
        },
        "preferred_amenities": preferences.preferred_amenities or [],
        "notifications": {
            "new_listings": preferences.notify_new_listings,
            "price_changes": preferences.notify_price_changes,
        },
    }

    return summary
