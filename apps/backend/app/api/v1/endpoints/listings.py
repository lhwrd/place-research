"""Listing ingest endpoints for the iOS Shortcut (writes to Baserow)."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from starlette.datastructures import UploadFile

from app.api import deps
from app.exceptions import ExternalAPIError
from app.schemas.listing import (
    ListingCreateRequest,
    ListingCreateResponse,
    ListingImagesResponse,
)
from app.services.baserow_enrichment import (
    BaserowEnrichmentService,
    ImageUpload,
    RowNotFoundError,
    get_baserow_service,
)

router = APIRouter(dependencies=[Depends(deps.verify_ingest_token)])
logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_IMAGES_PER_REQUEST = 50


@router.post(
    "",
    response_model=ListingCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Add a Zillow listing to Baserow",
    description="Creates a Properties row (or returns the existing one for the same zpid)",
)
async def create_listing(
    request: ListingCreateRequest,
    service: BaserowEnrichmentService = Depends(get_baserow_service),
):
    """
    Add a listing shared from Zillow.

    - **url**: Zillow listing URL
    - **listing_json**: Optional JSON scraped from the page, used for price, beds, etc.

    Enrichment starts when Baserow's webhook fires for the new row.
    """
    try:
        row_id, created = await service.create_listing(request.url, request.listing_json)
    except ExternalAPIError as e:
        logger.error("Baserow error creating listing: %s", e.message, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=e.message) from e
    return ListingCreateResponse(row_id=row_id, created=created)


@router.post(
    "/{row_id}/images",
    response_model=ListingImagesResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach photos to a listing",
    description="Upload one or more images and append them to the row's Photos field. "
    "Send multipart/form-data with one or more `file` parts, or a raw image body "
    "with its Content-Type (e.g. image/jpeg).",
)
async def upload_listing_images(
    row_id: int,
    request: Request,
    filename: Optional[str] = Query(None, description="File name for a raw-body upload"),
    service: BaserowEnrichmentService = Depends(get_baserow_service),
):
    """Attach photos to a Baserow listing row."""
    images = await _read_images(request, filename or f"listing-{row_id}")

    try:
        photo_count = await service.add_images(row_id, images)
    except RowNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Listing row {row_id} not found"
        ) from e
    except ExternalAPIError as e:
        logger.error("Baserow error uploading images: %s", e.message, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=e.message) from e

    return ListingImagesResponse(row_id=row_id, uploaded=len(images), photo_count=photo_count)


async def _read_images(request: Request, default_name: str) -> List[ImageUpload]:
    """Read images from a multipart form (`file` parts) or a raw request body."""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        uploads = [f for f in form.getlist("file") if isinstance(f, UploadFile)]
        if not uploads:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No `file` parts in form"
            )
        if len(uploads) > MAX_IMAGES_PER_REQUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"At most {MAX_IMAGES_PER_REQUEST} images per request",
            )
        images = []
        for i, upload in enumerate(uploads):
            data = await upload.read()
            images.append(
                _validated(
                    data,
                    upload.filename or f"{default_name}-{i + 1}",
                    upload.content_type or "",
                )
            )
        return images

    data = await request.body()
    return [_validated(data, default_name, content_type.split(";")[0].strip())]


def _validated(data: bytes, filename: str, content_type: str) -> ImageUpload:
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Expected an image, got {content_type or 'no Content-Type'}",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )
    if "." not in filename:
        filename = f"{filename}.{content_type.split('/')[-1]}"
    return ImageUpload(content=data, filename=filename, content_type=content_type)
