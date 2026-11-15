"""Listing ingest endpoints for the iOS Shortcut."""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from starlette.datastructures import UploadFile

from app.api import deps
from app.schemas.listing import (
    ListingCreateRequest,
    ListingCreateResponse,
    ListingImagesResponse,
)
from app.services.property_service import (
    ImageUpload,
    PropertyNotFoundError,
    PropertyService,
    get_property_service,
)

router = APIRouter(dependencies=[Depends(deps.verify_ingest_token)])
logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 25 * 1024 * 1024
# Photo formats only: SVG and other "images" can carry script, and photos are served from
# the app's own origin
ALLOWED_IMAGE_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif", "image/avif"}
)
MAX_IMAGES_PER_REQUEST = 50


@router.post(
    "",
    response_model=ListingCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Add a Zillow listing",
    description="Saves the listing (or returns the existing one for the same zpid) and "
    "starts enrichment in the background",
)
async def create_listing(
    request: ListingCreateRequest,
    background_tasks: BackgroundTasks,
    service: PropertyService = Depends(get_property_service),
):
    """
    Add a listing shared from Zillow.

    - **url**: Zillow listing URL
    - **listing_json**: Optional JSON scraped from the page, used for price, beds, etc.
    """
    property_id, created = service.create_listing(request.url, request.listing_json)
    if created:
        background_tasks.add_task(service.enrich_safely, property_id)
    return ListingCreateResponse(row_id=property_id, created=created)


@router.post(
    "/{row_id}/images",
    response_model=ListingImagesResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach photos to a listing",
    description="Upload one or more images and add them to the listing's photos. "
    "Send multipart/form-data with one or more `file` parts, or a raw image body "
    "with its Content-Type (e.g. image/jpeg).",
)
async def upload_listing_images(
    row_id: int,
    request: Request,
    filename: Optional[str] = Query(None, description="File name for a raw-body upload"),
    service: PropertyService = Depends(get_property_service),
):
    """Attach photos to a listing."""
    images = await read_images(request, filename or f"listing-{row_id}")

    try:
        photo_count = service.add_images(row_id, images)
    except PropertyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Listing {row_id} not found"
        ) from e

    return ListingImagesResponse(row_id=row_id, uploaded=len(images), photo_count=photo_count)


async def read_images(request: Request, default_name: str) -> List[ImageUpload]:
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
                validated_image(
                    data,
                    upload.filename or f"{default_name}-{i + 1}",
                    upload.content_type or "",
                )
            )
        return images

    data = await request.body()
    return [validated_image(data, default_name, content_type.split(";")[0].strip())]


def validated_image(data: bytes, filename: str, content_type: str) -> ImageUpload:
    content_type = content_type.lower()
    if content_type == "image/jpg":  # common mislabel
        content_type = "image/jpeg"
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Expected a JPEG, PNG, GIF, WebP, HEIC or AVIF photo, got "
            f"{content_type or 'no Content-Type'}",
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
