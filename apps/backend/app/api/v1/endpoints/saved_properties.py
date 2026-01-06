"""Saved properties endpoints for managing user's favorite properties."""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.exceptions import (
    DuplicatePropertyError,
    NotFoundError,
    PropertyNotFoundError,
)
from app.models.user import User
from app.schemas.saved_property import (
    SavedPropertyCreate,
    SavedPropertyList,
    SavedPropertyResponse,
    SavedPropertyStats,
    SavedPropertyUpdate,
    SavedPropertyWithDetails,
)
from app.services.saved_property_service import SavedPropertyService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=SavedPropertyList,
    summary="Get all saved properties",
    description="Get list of all saved properties for the current user",
)
async def get_saved_properties(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
    is_archived: Optional[bool] = Query(None, description="Filter by archived status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    sort_by: str = Query("saved_at", description="Sort field (saved_at, rating, updated_at)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all saved properties for the current user.

    Supports filtering by:
    - Favorite status
    - Archived status
    - Tags

    Supports sorting by:
    - saved_at (when property was saved)
    - rating (user rating)
    - updated_at (last update time)
    """
    saved_property_service = SavedPropertyService(db)

    # Parse tags if provided
    tag_list = None
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]

    # Get saved properties
    saved_properties, total = saved_property_service.get_user_saved_properties(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        is_favorite=is_favorite,
        is_archived=is_archived,
        tags=tag_list,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return SavedPropertyList(
        items=[SavedPropertyWithDetails.from_saved_property(sp) for sp in saved_properties],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=SavedPropertyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a property",
    description="Add a property to saved properties",
)
async def save_property(
    saved_data: SavedPropertyCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Save a property to your favorites.

    Required:
    - property_id: ID of the property to save

    Optional:
    - notes: Personal notes about the property
    - rating: Your rating (1-5 stars)
    - tags: Tags for organization (e.g., "close-to-work,great-schools")
    - is_favorite: Mark as favorite
    """
    saved_property_service = SavedPropertyService(db)

    # Check if property exists
    from app.services.property_service import PropertyService

    property_service = PropertyService(db)

    property_data = await property_service.get_property_by_id(
        property_id=saved_data.property_id, user_id=current_user.id
    )

    if not property_data:
        raise PropertyNotFoundError(property_id=saved_data.property_id)

    # Check if already saved
    existing = saved_property_service.get_saved_property(
        user_id=current_user.id, property_id=saved_data.property_id
    )

    if existing:
        raise DuplicatePropertyError(property_id=saved_data.property_id)

    # Save property
    saved_property = saved_property_service.save_property(
        user_id=current_user.id,
        property_id=saved_data.property_id,
        notes=saved_data.notes,
        rating=saved_data.rating,
        tags=saved_data.tags,
        is_favorite=saved_data.is_favorite,
    )

    logger.info(f"User {current_user.id} saved property {saved_data.property_id}")

    return SavedPropertyResponse.from_orm(saved_property)


@router.get(
    "/{saved_property_id}",
    response_model=SavedPropertyWithDetails,
    summary="Get saved property by ID",
    description="Get details of a specific saved property",
)
async def get_saved_property(
    saved_property_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific saved property with full property details.
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.get_saved_property_by_id(
        saved_property_id=saved_property_id, user_id=current_user.id
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyWithDetails.from_saved_property(saved_property)


@router.put(
    "/{saved_property_id}",
    response_model=SavedPropertyResponse,
    summary="Update saved property",
    description="Update notes, rating, tags, etc.  for a saved property",
)
async def update_saved_property(
    saved_property_id: int,
    update_data: SavedPropertyUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update saved property information.

    You can update:
    - notes:  Personal notes
    - rating: Your rating (1-5 stars)
    - tags: Organization tags
    - is_favorite:  Favorite status
    - is_archived: Archive status
    - viewed_in_person: Whether you've viewed it
    - viewing_date: Date of viewing
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id,
        user_id=current_user.id,
        updates=update_data.dict(exclude_unset=True),
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    logger.info(f"User {current_user.id} updated saved property {saved_property_id}")

    return SavedPropertyResponse.from_orm(saved_property)


@router.delete(
    "/{saved_property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove saved property",
    description="Remove a property from saved properties",
)
async def unsave_property(
    saved_property_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Remove a property from your saved properties.

    This permanently deletes the saved property record including all notes and ratings.
    """
    saved_property_service = SavedPropertyService(db)

    deleted = saved_property_service.delete_saved_property(
        saved_property_id=saved_property_id, user_id=current_user.id
    )

    if not deleted:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    logger.info(f"User {current_user.id} removed saved property {saved_property_id}")

    return None


@router.patch(
    "/{saved_property_id}/favorite",
    response_model=SavedPropertyResponse,
    summary="Toggle favorite status",
    description="Mark or unmark a saved property as favorite",
)
async def toggle_favorite(
    saved_property_id: int,
    is_favorite: bool = Query(..., description="Set favorite status"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Toggle favorite status for a saved property.
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id,
        user_id=current_user.id,
        updates={"is_favorite": is_favorite},
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyResponse.from_orm(saved_property)


@router.patch(
    "/{saved_property_id}/archive",
    response_model=SavedPropertyResponse,
    summary="Toggle archive status",
    description="Archive or unarchive a saved property",
)
async def toggle_archive(
    saved_property_id: int,
    is_archived: bool = Query(..., description="Set archive status"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Archive or unarchive a saved property.

    Archived properties are hidden from default list view but not deleted.
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id,
        user_id=current_user.id,
        updates={"is_archived": is_archived},
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyResponse.from_orm(saved_property)


@router.patch(
    "/{saved_property_id}/rating",
    response_model=SavedPropertyResponse,
    summary="Update rating",
    description="Update the rating for a saved property",
)
async def update_rating(
    saved_property_id: int,
    rating: int = Query(..., ge=1, le=5, description="Rating (1-5 stars)"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update rating for a saved property.

    Rating must be between 1 and 5 stars.
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id,
        user_id=current_user.id,
        updates={"rating": rating},
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyResponse.from_orm(saved_property)


@router.patch(
    "/{saved_property_id}/notes",
    response_model=SavedPropertyResponse,
    summary="Update notes",
    description="Update notes for a saved property",
)
async def update_notes(
    saved_property_id: int,
    notes: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update notes for a saved property.
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id,
        user_id=current_user.id,
        updates={"notes": notes},
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyResponse.from_orm(saved_property)


@router.patch(
    "/{saved_property_id}/tags",
    response_model=SavedPropertyResponse,
    summary="Update tags",
    description="Update tags for a saved property",
)
async def update_tags(
    saved_property_id: int,
    tags: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update tags for a saved property.

    Provide tags as comma-separated string (e.g., "favorite,close-to-work,good-schools").
    """
    saved_property_service = SavedPropertyService(db)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id,
        user_id=current_user.id,
        updates={"tags": tags},
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyResponse.from_orm(saved_property)


@router.post(
    "/{saved_property_id}/viewed",
    response_model=SavedPropertyResponse,
    summary="Mark as viewed in person",
    description="Mark that you've viewed this property in person",
)
async def mark_as_viewed(
    saved_property_id: int,
    viewing_date: Optional[str] = Query(None, description="Date of viewing (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Mark a property as viewed in person.

    Optionally provide the viewing date.
    """
    from datetime import datetime, timezone

    saved_property_service = SavedPropertyService(db)

    updates = {"viewed_in_person": True}

    if viewing_date:
        try:
            parsed_date = datetime.fromisoformat(viewing_date)
            updates["viewing_date"] = parsed_date
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )
    else:
        updates["viewing_date"] = datetime.now(timezone.utc)

    saved_property = saved_property_service.update_saved_property(
        saved_property_id=saved_property_id, user_id=current_user.id, updates=updates
    )

    if not saved_property:
        raise NotFoundError(f"Saved property {saved_property_id} not found")

    return SavedPropertyResponse.from_orm(saved_property)


@router.get(
    "/favorites/list",
    response_model=SavedPropertyList,
    summary="Get favorite properties",
    description="Get only properties marked as favorites",
)
async def get_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all favorite properties (is_favorite = True).
    """
    saved_property_service = SavedPropertyService(db)

    saved_properties, total = saved_property_service.get_user_saved_properties(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        is_favorite=True,
        is_archived=False,
    )

    return SavedPropertyList(
        items=[SavedPropertyWithDetails.from_saved_property(sp) for sp in saved_properties],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats/summary",
    response_model=SavedPropertyStats,
    summary="Get saved properties statistics",
    description="Get statistics about your saved properties",
)
async def get_saved_properties_stats(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get statistics about saved properties.

    Returns:
    - Total saved properties
    - Number of favorites
    - Number archived
    - Number viewed in person
    - Average rating
    - Most used tags
    """
    saved_property_service = SavedPropertyService(db)
    stats = saved_property_service.get_user_stats(current_user.id)

    return SavedPropertyStats(**stats)


@router.get(
    "/tags/list",
    summary="Get all tags",
    description="Get list of all tags used in saved properties",
)
async def get_all_tags(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get all unique tags used in your saved properties.

    Returns a list of tags with usage count.
    """
    saved_property_service = SavedPropertyService(db)
    tags = saved_property_service.get_all_tags(current_user.id)

    return {"tags": tags}


@router.post(
    "/bulk/archive",
    summary="Bulk archive properties",
    description="Archive multiple properties at once",
)
async def bulk_archive(
    saved_property_ids: List[int],
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Archive multiple saved properties at once.
    """
    saved_property_service = SavedPropertyService(db)

    updated_count = saved_property_service.bulk_update(
        user_id=current_user.id,
        saved_property_ids=saved_property_ids,
        updates={"is_archived": True},
    )

    return {"message": f"Archived {updated_count} properties", "count": updated_count}


@router.post(
    "/bulk/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bulk delete properties",
    description="Delete multiple saved properties at once",
)
async def bulk_delete(
    saved_property_ids: List[int],
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete multiple saved properties at once.
    """
    saved_property_service = SavedPropertyService(db)

    deleted_count = saved_property_service.bulk_delete(
        user_id=current_user.id, saved_property_ids=saved_property_ids
    )

    logger.info(f"User {current_user.id} bulk deleted {deleted_count} properties")

    return None


@router.get(
    "/compare/list",
    summary="Get properties for comparison",
    description="Get multiple properties for side-by-side comparison",
)
async def get_properties_for_comparison(
    saved_property_ids: str = Query(..., description="Comma-separated saved property IDs"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get multiple saved properties for comparison.

    Provide up to 5 property IDs for side-by-side comparison.
    """
    # Parse IDs
    try:
        ids = [int(id.strip()) for id in saved_property_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid property IDs")

    if len(ids) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare more than 5 properties at once",
        )

    saved_property_service = SavedPropertyService(db)

    properties = []
    for property_id in ids:
        saved_property = saved_property_service.get_saved_property_by_id(
            saved_property_id=property_id, user_id=current_user.id
        )
        if saved_property:
            properties.append(SavedPropertyWithDetails.from_saved_property(saved_property))

    return {"properties": properties, "count": len(properties)}
