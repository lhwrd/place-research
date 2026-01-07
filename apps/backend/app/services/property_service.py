"""Property service for managing property search and CRUD operations."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.exceptions import (
    InvalidAddressError,
    PropertyAccessDeniedError,
)
from app.integrations.property_data_factory import get_property_data_api
from app.models.property import Property
from app.schemas.property import PropertyData
from app.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class PropertyService:
    """Service for property-related operations."""

    def __init__(self, db: Session):
        self.db = db
        self.geocoding_service = GeocodingService()
        self.property_data_api = get_property_data_api()

    async def search_by_address(self, address: str, user_id: int) -> PropertyData:
        """
        Search for a property by address.

        Workflow:
        1. Check if property already exists in database (for this user or cached)
        2. If not, geocode the address
        3. Fetch property data from external API
        4. Save to database
        5. Return property data

        Args:
            address: Full street address
            user_id: ID of the user searching

        Returns:
            PropertyData object

        Raises:
            InvalidAddressError: If address cannot be geocoded
            PropertyNotFoundError: If property data cannot be found
        """
        # Step 1: Check if property already exists
        existing_property = await self._find_existing_property(address, user_id)
        if existing_property:
            logger.info("Property found in cache: %s", existing_property.id)
            return PropertyData.model_validate(existing_property)

        # Step 2: Geocode the address
        try:
            geocode_result = await self.geocoding_service.geocode_address(address)
        except Exception as e:
            logger.error("Geocoding failed for address %s:  %s", address, str(e))
            raise InvalidAddressError(address=address, reason="Unable to geocode address")

        if not geocode_result:
            raise InvalidAddressError(address=address, reason="Address not found")

        # Step 3: Fetch property data from external API
        try:
            property_data = await self.property_data_api.get_property_details(
                latitude=geocode_result["latitude"],
                longitude=geocode_result["longitude"],
                address=address,
            )
        except Exception as e:
            logger.error("Property data fetch failed:  %s", str(e))
            # Create minimal property record with just geocoded data
            property_data = {
                "address": geocode_result.get("formatted_address", address),
                "city": geocode_result.get("city"),
                "state": geocode_result.get("state"),
                "zip_code": geocode_result.get("zip_code"),
                "county": geocode_result.get("county"),
            }

        # Step 4: Save to database
        property_record = await self._create_property(
            user_id=user_id,
            latitude=geocode_result["latitude"],
            longitude=geocode_result["longitude"],
            property_data=property_data,
        )

        logger.info("Created new property record: %s", property_record.id)
        return PropertyData.model_validate(property_record)

    async def get_property_by_id(self, property_id: int, user_id: int) -> Optional[PropertyData]:
        """
        Get a specific property by ID.

        Args:
            property_id: ID of the property
            user_id: ID of the requesting user

        Returns:
            PropertyData if found, None otherwise

        Raises:
            PropertyAccessDeniedError: If user doesn't have access
        """
        property_record = self.db.query(Property).filter(Property.id == property_id).first()

        if not property_record:
            return None

        # Check if user has access (owns the property or it's shared)
        if property_record.user_id != user_id:
            # Could add logic here for shared properties
            raise PropertyAccessDeniedError(property_id=property_id)

        return PropertyData.model_validate(property_record)

    async def get_user_properties(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[PropertyData]:
        """
        Get all properties for a user.

        Args:
            user_id: ID of the user
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of PropertyData objects
        """
        properties = (
            self.db.query(Property)
            .filter(Property.user_id == user_id)
            .order_by(Property.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return [PropertyData.model_validate(prop) for prop in properties]

    async def delete_property(self, property_id: int, user_id: int) -> bool:
        """
        Delete a property from user's search history.

        Args:
            property_id: ID of the property to delete
            user_id: ID of the user

        Returns:
            True if deleted, False if not found
        """
        property_record = (
            self.db.query(Property)
            .filter(and_(Property.id == property_id, Property.user_id == user_id))
            .first()
        )

        if not property_record:
            return False

        self.db.delete(property_record)
        self.db.commit()

        logger.info("Deleted property %s for user %s", property_id, user_id)
        return True

    async def update_property(
        self, property_id: int, user_id: int, updates: dict
    ) -> Optional[PropertyData]:
        """
        Update property information.

        Args:
            property_id: ID of the property
            user_id: ID of the user
            updates: Dictionary of fields to update

        Returns:
            Updated PropertyData or None if not found
        """
        property_record = (
            self.db.query(Property)
            .filter(and_(Property.id == property_id, Property.user_id == user_id))
            .first()
        )

        if not property_record:
            return None

        for key, value in updates.items():
            if hasattr(property_record, key):
                setattr(property_record, key, value)

        property_record.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(property_record)

        return PropertyData.model_validate(property_record)

    # Private helper methods

    async def _find_existing_property(self, address: str, user_id: int) -> Optional[Property]:
        """
        Find existing property by address.
        First checks user's own properties, then shared/cached properties.
        """
        # Normalize address for comparison
        normalized_address = address.strip().lower()

        # Check user's properties
        property_record = (
            self.db.query(Property)
            .filter(
                and_(
                    Property.user_id == user_id,
                    Property.address.ilike(f"%{normalized_address}%"),
                )
            )
            .first()
        )

        if property_record:
            return property_record

        # Could add logic to check for similar addresses from other users
        # (with appropriate privacy controls)

        return None

    async def _create_property(
        self, user_id: int, latitude: float, longitude: float, property_data: dict
    ) -> Property:
        """Create a new property record in the database."""
        property_record = Property(
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            address=property_data.get("address"),
            city=property_data.get("city"),
            state=property_data.get("state"),
            zip_code=property_data.get("zip_code"),
            county=property_data.get("county"),
            bedrooms=property_data.get("bedrooms"),
            bathrooms=property_data.get("bathrooms"),
            square_feet=property_data.get("square_feet"),
            lot_size=property_data.get("lot_size"),
            year_built=property_data.get("year_built"),
            property_type=property_data.get("property_type"),
            estimated_value=property_data.get("estimated_value"),
            last_sold_price=property_data.get("last_sold_price"),
            last_sold_date=property_data.get("last_sold_date"),
            tax_assessed_value=property_data.get("tax_assessed_value"),
            annual_tax=property_data.get("annual_tax"),
            description=property_data.get("description"),
            parcel_id=property_data.get("parcel_id"),
            zillow_id=property_data.get("zillow_id"),
        )

        self.db.add(property_record)
        self.db.commit()
        self.db.refresh(property_record)

        return property_record
