from fastapi import APIRouter

from app.api.v1.endpoints import auth, locations, properties, saved_properties, user_preferences

api_router = APIRouter()

# Authentication routes (no auth required)
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Property search and enrichment routes
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])

# User preferences configuration
api_router.include_router(user_preferences.router, prefix="/preferences", tags=["user-preferences"])

# Saved properties management
api_router.include_router(
    saved_properties.router, prefix="/saved-properties", tags=["saved-properties"]
)

# Custom locations (family/friends addresses)
api_router.include_router(locations.router, prefix="/locations", tags=["custom-locations"])
