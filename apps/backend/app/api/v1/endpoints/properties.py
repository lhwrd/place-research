import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.models.user import User
from app.schemas.property import (
    PropertyEnrichmentResponse,
    PropertySearchRequest,
    PropertySearchResponse,
)
from app.services.enrichment.orchestrator import EnrichmentOrchestrator
from app.services.property_service import PropertyService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/search",
    response_model=PropertySearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for a property by address",
    description="Returns basic property information for a given address",
)
async def search_property(
    request: PropertySearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Search for a property by address.

    - **address**:  Full street address (e.g., "123 Main St, Seattle, WA 98101")

    Returns basic property data without enrichment.
    Use the /enrich endpoint for detailed analysis.
    """
    property_service = PropertyService(db)

    try:
        property_data = await property_service.search_by_address(
            address=request.address, user_id=current_user.id
        )

        if not property_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property not found for address:  {request.address}",
            )

        return PropertySearchResponse(
            success=True, property=property_data, message="Property found successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("ValueError in search_property: %s", str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error("Exception in search_property: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for the property",
        ) from e


@router.post(
    "/{property_id}/enrich",
    response_model=PropertyEnrichmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Enrich property with detailed analysis",
    description="Enriches property with walk score, nearby amenities, and distances to custom locations",  # pylint: disable=line-too-long
)
async def enrich_property(
    property_id: int,
    use_cached: bool = Query(
        default=True,
        description="Use cached enrichment data if available (less than 30 days old)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Enrich a property with detailed analysis based on user preferences.

    This endpoint will:
    - Calculate walk score and bike score
    - Find nearest grocery stores, parks, restaurants, etc.
    - Calculate driving distance/time to user's custom locations (family/friends)
    - Apply user preference filters

    **Note**: This is a rate-limited endpoint due to external API costs.
    Users are limited to 10 enrichments per hour.
    """
    property_service = PropertyService(db)
    enrichment_orchestrator = EnrichmentOrchestrator(db)

    # Verify property exists and belongs to user or is accessible
    property_data = await property_service.get_property_by_id(
        property_id=property_id, user_id=current_user.id
    )

    if not property_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    try:
        # Orchestrate all enrichment services
        enrichment_data = await enrichment_orchestrator.enrich_property(
            property_id=property_id, user_id=current_user.id, use_cached=use_cached
        )

        return PropertyEnrichmentResponse(
            success=True,
            property_id=property_id,
            enrichment=enrichment_data,
            message="Property enriched successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich property:  {str(e)}",
        ) from e


@router.get(
    "/{property_id}",
    response_model=PropertySearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get property by ID",
)
async def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Retrieve a specific property by its ID.
    """
    property_service = PropertyService(db)

    property_data = await property_service.get_property_by_id(
        property_id=property_id, user_id=current_user.id
    )

    if not property_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    return PropertySearchResponse(
        success=True, property=property_data, message="Property retrieved successfully"
    )


@router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a property from search history",
)
async def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Delete a property from the user's search history.

    Note: This only removes it from your history, not from saved properties.
    """
    property_service = PropertyService(db)

    deleted = await property_service.delete_property(
        property_id=property_id, user_id=current_user.id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found or already deleted",
        )

    return None
