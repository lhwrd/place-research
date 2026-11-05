from fastapi import APIRouter

from app.api.v1.endpoints import listings, webhooks

api_router = APIRouter()

# Listing ingest from the iOS Shortcut
api_router.include_router(listings.router, prefix="/listings", tags=["listings"])

# Baserow webhooks that trigger enrichment
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
