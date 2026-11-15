from fastapi import APIRouter

from app.api.v1.endpoints import listings

api_router = APIRouter()

# Listing ingest from the iOS Shortcut
api_router.include_router(listings.router, prefix="/listings", tags=["listings"])
