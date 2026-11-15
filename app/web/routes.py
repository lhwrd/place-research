"""Server-rendered web UI: property list and detail, drive-time locations, settings.

Plain HTML forms that POST and redirect back. There is no login; the UI is meant to be
reached only over the tailnet.
"""

from pathlib import Path
from typing import List, Optional
from urllib.parse import quote, urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile

from app.api.v1.endpoints.listings import MAX_IMAGES_PER_REQUEST, validated_image
from app.core.config import settings
from app.db import PropertyStatus
from app.db.database import LOCATION_TYPES, PROPERTY_SORTS
from app.services.property_service import (
    AMENITY_TYPES,
    PREFERRED_PLACES,
    PropertyService,
    get_property_service,
)
from app.services.property_view import build_view

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

SORT_LABELS = {
    "newest": "Newest",
    "price": "Price ↑",
    "price_desc": "Price ↓",
    "rating": "Rating",
    "neighborhood": "Neighborhood",
    "address": "Address",
}


def _money(value) -> str:
    return f"${value:,.0f}" if value is not None else "—"


def _num(value, places: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value:,.{places}f}".rstrip("0").rstrip(".") if places else f"{value:,.0f}"


def garage(spaces) -> str:
    """0 -> "No garage", 2 -> "2-car garage"."""
    return "No garage" if spaces == 0 else f"{spaces}-car garage"


def duration(minutes) -> str:
    """Minutes as "45m", "1h 30m" or "2h"."""
    if minutes is None:
        return "—"
    hours, mins = divmod(round(float(minutes)), 60)
    if not hours:
        return f"{mins}m"
    return f"{hours}h {mins}m" if mins else f"{hours}h"


templates.env.filters["money"] = _money
templates.env.filters["duration"] = duration
templates.env.filters["garage"] = garage
templates.env.filters["num"] = _num
templates.env.filters["urlquote"] = lambda s: quote(str(s or ""))


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def _get_property_or_404(service: PropertyService, property_id: int):
    prop = service.db.get_property(property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


# Properties


@router.get("/", response_class=HTMLResponse)
async def property_list(
    request: Request,
    sort: str = "newest",
    service: PropertyService = Depends(get_property_service),
):
    sort = sort if sort in PROPERTY_SORTS else "newest"
    properties = service.db.list_properties(sort)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "properties": properties,
            "sort": sort,
            "sort_labels": SORT_LABELS,
            "pending": any(p["status"] in PropertyStatus.PENDING for p in properties),
        },
    )


@router.post("/properties")
async def add_property(
    background_tasks: BackgroundTasks,
    query: str = Form(...),
    service: PropertyService = Depends(get_property_service),
):
    if not query.strip():
        return _redirect("/")
    property_id, created = service.create_from_input(query)
    if created:
        background_tasks.add_task(service.enrich_safely, property_id)
    return _redirect(f"/properties/{property_id}")


@router.get("/properties/{property_id}", response_class=HTMLResponse)
async def property_detail(
    request: Request,
    property_id: int,
    service: PropertyService = Depends(get_property_service),
):
    prop = _get_property_or_404(service, property_id)
    return templates.TemplateResponse(
        request,
        "property.html",
        {
            "p": prop,
            "view": build_view(prop["enrichment"]),
            "photo_ids": service.db.photo_ids(property_id),
            "pending": prop["status"] in PropertyStatus.PENDING,
            "street_view_url": street_view_url(prop),
        },
    )


STREET_VIEW_EMBED = "https://www.google.com/maps/embed/v1/streetview"


def street_view_url(prop) -> Optional[str]:
    """
    Maps Embed API URL for an interactive Street View of the property, or None if there's
    no key, no location yet, or no coverage.

    Starts at the panorama found during enrichment, facing the house; properties enriched
    before that use the location and let Google pick the panorama and direction.
    """
    key = settings.google_maps_embed_key or settings.google_maps_api_key
    if not key or prop.get("latitude") is None:
        return None
    pano = (prop.get("enrichment") or {}).get("street_view_provider") or {}
    if pano.get("available") is False:
        return None
    params = {"key": key, "fov": 80, "pitch": 0}
    if pano.get("pano_id"):
        params["pano"] = pano["pano_id"]
        if pano.get("heading") is not None:
            params["heading"] = pano["heading"]
    else:
        params["location"] = f"{prop['latitude']},{prop['longitude']}"
    return f"{STREET_VIEW_EMBED}?{urlencode(params)}"


@router.get("/properties/{property_id}/status")
async def property_status(
    property_id: int, service: PropertyService = Depends(get_property_service)
):
    """Polled by the detail page while enrichment runs."""
    return {"status": _get_property_or_404(service, property_id)["status"]}


@router.post("/properties/{property_id}/notes")
async def save_notes(
    property_id: int,
    notes: str = Form(""),
    rating: str = Form(""),
    visited: Optional[str] = Form(None),
    service: PropertyService = Depends(get_property_service),
):
    _get_property_or_404(service, property_id)
    service.db.update_property(
        property_id,
        {
            "notes": notes.strip(),
            "rating": _stars(rating),
            "visited": visited is not None,
        },
    )
    return _redirect(f"/properties/{property_id}#notes")


@router.post("/properties/{property_id}/neighborhood")
async def save_neighborhood_rating(
    property_id: int,
    neighborhood_rating: str = Form(""),
    service: PropertyService = Depends(get_property_service),
):
    _get_property_or_404(service, property_id)
    service.db.update_property(property_id, {"neighborhood_rating": _stars(neighborhood_rating)})
    return _redirect(f"/properties/{property_id}#street-view")


def _stars(value: str) -> Optional[int]:
    """A 1-5 rating from a form, or None (cleared or invalid)."""
    return int(value) if value.isdigit() and 1 <= int(value) <= 5 else None


@router.post("/properties/{property_id}/facts")
async def save_facts(
    property_id: int,
    address: str = Form(...),
    price: str = Form(""),
    beds: str = Form(""),
    baths: str = Form(""),
    sqft: str = Form(""),
    year_built: str = Form(""),
    garage_spaces: str = Form(""),
    service: PropertyService = Depends(get_property_service),
):
    """Hand-edit listing facts (mostly for properties added by address)."""
    prop = _get_property_or_404(service, property_id)
    service.db.update_property(
        property_id,
        {
            "address": address.strip() or prop["address"],
            "price": _int(price),
            "beds": _float(beds),
            "baths": _float(baths),
            "sqft": _int(sqft),
            "year_built": _int(year_built),
            "garage_spaces": _int(garage_spaces),
        },
    )
    return _redirect(f"/properties/{property_id}")


@router.post("/properties/{property_id}/reenrich")
async def reenrich(
    property_id: int,
    background_tasks: BackgroundTasks,
    service: PropertyService = Depends(get_property_service),
):
    _get_property_or_404(service, property_id)
    service.db.update_property(property_id, {"status": PropertyStatus.NEW})
    background_tasks.add_task(service.enrich_safely, property_id, use_cached=False)
    return _redirect(f"/properties/{property_id}")


@router.post("/properties/{property_id}/delete")
async def delete_property(
    property_id: int, service: PropertyService = Depends(get_property_service)
):
    service.db.delete_property(property_id)
    return _redirect("/")


@router.post("/properties/{property_id}/photos")
async def upload_photos(
    request: Request,
    property_id: int,
    service: PropertyService = Depends(get_property_service),
):
    _get_property_or_404(service, property_id)
    form = await request.form()
    uploads: List[UploadFile] = [
        f for f in form.getlist("file") if isinstance(f, UploadFile) and f.filename
    ]
    if len(uploads) > MAX_IMAGES_PER_REQUEST:
        raise HTTPException(400, f"At most {MAX_IMAGES_PER_REQUEST} images at a time")
    images = [
        validated_image(await u.read(), u.filename or "photo", u.content_type or "")
        for u in uploads
    ]
    if images:
        service.add_images(property_id, images)
    return _redirect(f"/properties/{property_id}#photos")


@router.get("/photos/{photo_id}")
async def photo(photo_id: int, service: PropertyService = Depends(get_property_service)):
    found = service.db.get_photo(photo_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    # Photos never change once stored, so browsers can keep them. Serve them inert: never
    # sniffed as another type, and sandboxed so nothing in a file can run as this site.
    return Response(
        found.data,
        media_type=found.content_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/photos/{photo_id}/delete")
async def delete_photo(photo_id: int, service: PropertyService = Depends(get_property_service)):
    found = service.db.get_photo(photo_id)
    if found is None:
        return _redirect("/")
    service.db.delete_photo(photo_id)
    return _redirect(f"/properties/{found.property_id}#photos")


# Drive-time locations


@router.get("/locations", response_class=HTMLResponse)
async def locations(request: Request, service: PropertyService = Depends(get_property_service)):
    return templates.TemplateResponse(
        request,
        "locations.html",
        {"locations": service.db.list_locations(), "types": LOCATION_TYPES},
    )


@router.post("/locations")
async def add_location(
    name: str = Form(...),
    address: str = Form(...),
    type: str = Form(""),
    priority: str = Form("0"),
    service: PropertyService = Depends(get_property_service),
):
    if name.strip() and address.strip():
        service.db.create_location(_location_values(name, address, type, priority, True))
    return _redirect("/locations")


@router.post("/locations/{location_id}")
async def update_location(
    location_id: int,
    name: str = Form(...),
    address: str = Form(...),
    type: str = Form(""),
    priority: str = Form("0"),
    active: Optional[str] = Form(None),
    service: PropertyService = Depends(get_property_service),
):
    if name.strip() and address.strip():
        service.db.update_location(
            location_id, _location_values(name, address, type, priority, active is not None)
        )
    return _redirect("/locations")


@router.post("/locations/{location_id}/delete")
async def delete_location(
    location_id: int, service: PropertyService = Depends(get_property_service)
):
    service.db.delete_location(location_id)
    return _redirect("/locations")


def _location_values(name: str, address: str, type_: str, priority: str, active: bool):
    return {
        "name": name.strip(),
        "address": address.strip(),
        "type": type_ if type_ in LOCATION_TYPES else None,
        "priority": _int(priority) or 0,
        "active": int(active),
    }


# Settings


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request, saved: bool = False, service: PropertyService = Depends(get_property_service)
):
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "amenity_types": service.db.get_setting(AMENITY_TYPES),
            "preferred_places": service.db.get_setting(PREFERRED_PLACES),
            "saved": saved,
        },
    )


@router.post("/settings")
async def save_settings(
    amenity_types: str = Form(""),
    preferred_places: str = Form(""),
    service: PropertyService = Depends(get_property_service),
):
    service.db.set_setting(AMENITY_TYPES, amenity_types.strip())
    service.db.set_setting(PREFERRED_PLACES, preferred_places.strip())
    return _redirect("/settings?saved=1")


def _int(value: str) -> Optional[int]:
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        return int(float(cleaned)) if cleaned else None
    except ValueError:
        return None


def _float(value: str) -> Optional[float]:
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None
