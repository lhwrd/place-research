"""Unit tests for PropertyService."""

import pytest
from sqlalchemy.orm import Session

from app.services.property_service import PropertyService
from app.models.user import User
from tests.factories.user_factory import PropertyFactory


class TestPropertyService:
    """Test suite for PropertyService."""

    @pytest.mark.asyncio
    async def test_create_property(self, db: Session, test_user: User):
        """Test creating a property."""
        service = PropertyService(db)

        property_data = {
            "address": "123 Test St",
            "city": "Seattle",
            "state": "WA",
            "zip_code": "98101",
            "bedrooms": 3,
            "bathrooms": 2.0,
            "square_feet": 2000,
        }

        property_record = await service._create_property(
            user_id=test_user.id,
            latitude=47.6062,
            longitude=-122.3321,
            property_data=property_data,
        )

        assert property_record.id is not None
        assert property_record.user_id == test_user.id
        assert property_record.address == "123 Test St"
        assert property_record.bedrooms == 3

    @pytest.mark.asyncio
    async def test_get_property_by_id(self, db: Session, test_user: User):
        """Test retrieving a property by ID."""
        # Create test property
        property_record = PropertyFactory.create(db, test_user.id)

        # Retrieve it
        service = PropertyService(db)
        result = await service.get_property_by_id(property_record.id, test_user.id)

        assert result is not None
        assert result.id == property_record.id
        assert result.address == property_record.address

    @pytest.mark.asyncio
    async def test_get_property_by_id_not_found(self, db: Session, test_user: User):
        """Test retrieving non-existent property."""
        service = PropertyService(db)
        result = await service.get_property_by_id(99999, test_user.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_properties(self, db: Session, test_user: User):
        """Test retrieving all properties for a user."""
        # Create multiple properties
        PropertyFactory.create_batch(db, test_user.id, count=5)

        # Retrieve them
        service = PropertyService(db)
        properties = await service.get_user_properties(test_user.id)

        assert len(properties) == 5
        # Verify all returned objects are PropertyData instances with required fields
        assert all(isinstance(p, type(properties[0])) for p in properties)
        assert all(p.id is not None for p in properties)

    @pytest.mark.asyncio
    async def test_delete_property(self, db: Session, test_user: User):
        """Test deleting a property."""
        property_record = PropertyFactory.create(db, test_user.id)

        service = PropertyService(db)
        result = await service.delete_property(property_record.id, test_user.id)

        assert result is True

        # Verify it's deleted
        deleted = await service.get_property_by_id(property_record.id, test_user.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_update_property(self, db: Session, test_user: User):
        """Test updating a property."""
        property_record = PropertyFactory.create(db, test_user.id, bedrooms=3)

        service = PropertyService(db)
        updated = await service.update_property(
            property_id=property_record.id,
            user_id=test_user.id,
            updates={"bedrooms": 4, "bathrooms": 3.0},
        )

        assert updated is not None
        assert updated.bedrooms == 4
        assert updated.bathrooms == 3.0
