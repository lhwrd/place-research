"""Tests for saved properties endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.saved_properties import (
    bulk_archive,
    bulk_delete,
    get_properties_for_comparison,
    get_saved_properties,
    get_saved_property,
    mark_as_viewed,
    save_property,
    toggle_favorite,
    unsave_property,
    update_saved_property,
)
from app.exceptions import DuplicatePropertyError, NotFoundError, PropertyNotFoundError
from app.schemas.saved_property import (
    SavedPropertyCreate,
    SavedPropertyUpdate,
)


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = Mock()
    user.id = 1
    return user


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_property_data():
    """Create a mock property with proper data structure."""
    mock_property = Mock()
    mock_property.id = 123
    mock_property.address = "123 Main St"
    mock_property.city = "Seattle"
    mock_property.state = "WA"
    mock_property.zip_code = "98101"
    mock_property.latitude = 47.6062
    mock_property.longitude = -122.3321
    mock_property.bedrooms = 3
    mock_property.bathrooms = 2.0
    mock_property.square_feet = 2000
    mock_property.year_built = 2020
    mock_property.property_type = "Single Family"
    mock_property.estimated_value = 500000
    mock_property.county = "King"
    mock_property.lot_size = 5000
    mock_property.last_sold_price = 480000
    mock_property.last_sold_date = datetime(2022, 5, 20)
    mock_property.tax_assessed_value = 490000
    mock_property.annual_tax = 6000
    mock_property.description = "A lovely family home."
    mock_property.parcel_id = "9876543210"
    mock_property.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_property.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return mock_property


@pytest.fixture
def mock_saved_property(mock_property_data):
    """Create a mock saved property with proper structure."""
    mock_saved = Mock()
    mock_saved.id = 1
    mock_saved.user_id = 1
    mock_saved.property_id = 123
    mock_saved.notes = "Great property"
    mock_saved.rating = 5
    mock_saved.tags = "favorite,close-to-work"
    mock_saved.is_favorite = True
    mock_saved.is_archived = False
    mock_saved.viewed_in_person = False
    mock_saved.viewing_date = None
    mock_saved.saved_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_saved.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_saved.property = mock_property_data
    return mock_saved


@pytest.fixture
def mock_saved_property_service():
    """Mock SavedPropertyService."""
    with patch("app.api.v1.endpoints.saved_properties.SavedPropertyService") as mock:
        yield mock


@pytest.fixture
def mock_property_service():
    """Mock PropertyService."""
    with patch("app.services.property_service.PropertyService") as mock:
        yield mock


class TestGetSavedProperties:
    """Tests for get_saved_properties endpoint."""

    @pytest.mark.asyncio
    async def test_get_saved_properties_success(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_saved_property,
    ):
        """Test successful retrieval of saved properties."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_user_saved_properties.return_value = ([mock_saved_property], 1)

        result = await get_saved_properties(
            skip=0,
            limit=100,
            is_favorite=None,
            is_archived=None,
            tags=None,
            sort_by="saved_at",
            sort_order="desc",
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result.total == 1
        assert len(result.items) == 1
        mock_service.get_user_saved_properties.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_saved_properties_with_filters(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test retrieval with filters."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_user_saved_properties.return_value = ([], 0)

        await get_saved_properties(
            skip=0,
            limit=50,
            is_favorite=True,
            is_archived=False,
            tags="tag1,tag2",
            sort_by="rating",
            sort_order="asc",
            current_user=mock_current_user,
            db=mock_db,
        )

        call_args = mock_service.get_user_saved_properties.call_args
        assert call_args.kwargs["is_favorite"] is True
        assert call_args.kwargs["tags"] == ["tag1", "tag2"]


class TestSaveProperty:
    """Tests for save_property endpoint."""

    @pytest.mark.asyncio
    async def test_save_property_success(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_property_service,
        mock_saved_property,
    ):
        """Test successful property save."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_saved_property.return_value = None
        mock_service.save_property.return_value = mock_saved_property

        mock_prop_service = mock_property_service.return_value
        mock_prop_service.get_property_by_id = AsyncMock(return_value={"id": 123})

        saved_data = SavedPropertyCreate(property_id=123)

        result = await save_property(
            saved_data=saved_data,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result is not None
        mock_service.save_property.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_property_not_found(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_property_service,
    ):
        """Test saving non-existent property."""

        mock_prop_service = mock_property_service.return_value
        mock_prop_service.get_property_by_id = AsyncMock(return_value=None)

        saved_data = SavedPropertyCreate(property_id=999)

        with pytest.raises(PropertyNotFoundError):
            await save_property(
                saved_data=saved_data,
                current_user=mock_current_user,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_save_property_duplicate(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_property_service,
        mock_saved_property,
    ):
        """Test saving already saved property."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_saved_property.return_value = mock_saved_property

        mock_prop_service = mock_property_service.return_value
        mock_prop_service.get_property_by_id = AsyncMock(return_value={"id": 123})

        saved_data = SavedPropertyCreate(property_id=123)

        with pytest.raises(DuplicatePropertyError):
            await save_property(
                saved_data=saved_data,
                current_user=mock_current_user,
                db=mock_db,
            )


class TestGetSavedProperty:
    """Tests for get_saved_property endpoint."""

    @pytest.mark.asyncio
    async def test_get_saved_property_success(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_saved_property,
    ):
        """Test successful retrieval of specific saved property."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_saved_property_by_id.return_value = mock_saved_property

        result = await get_saved_property(
            saved_property_id=1,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result is not None
        mock_service.get_saved_property_by_id.assert_called_once_with(
            saved_property_id=1, user_id=mock_current_user.id
        )

    @pytest.mark.asyncio
    async def test_get_saved_property_not_found(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test retrieval of non-existent saved property."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_saved_property_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await get_saved_property(
                saved_property_id=999,
                current_user=mock_current_user,
                db=mock_db,
            )


class TestUpdateSavedProperty:
    """Tests for update_saved_property endpoint."""

    @pytest.mark.asyncio
    async def test_update_saved_property_success(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_saved_property,
    ):
        """Test successful update."""

        mock_service = mock_saved_property_service.return_value
        mock_service.update_saved_property.return_value = mock_saved_property

        update_data = SavedPropertyUpdate(notes="Updated notes")

        result = await update_saved_property(
            saved_property_id=1,
            update_data=update_data,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result is not None
        mock_service.update_saved_property.assert_called_once()


class TestUnsaveProperty:
    """Tests for unsave_property endpoint."""

    @pytest.mark.asyncio
    async def test_unsave_property_success(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test successful deletion."""

        mock_service = mock_saved_property_service.return_value
        mock_service.delete_saved_property.return_value = True

        result = await unsave_property(
            saved_property_id=1,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_unsave_property_not_found(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test deletion of non-existent property."""

        mock_service = mock_saved_property_service.return_value
        mock_service.delete_saved_property.return_value = False

        with pytest.raises(NotFoundError):
            await unsave_property(
                saved_property_id=999,
                current_user=mock_current_user,
                db=mock_db,
            )


class TestToggleFavorite:
    """Tests for toggle_favorite endpoint."""

    @pytest.mark.asyncio
    async def test_toggle_favorite_success(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_saved_property,
    ):
        """Test successful favorite toggle."""

        mock_service = mock_saved_property_service.return_value
        mock_service.update_saved_property.return_value = mock_saved_property

        await toggle_favorite(
            saved_property_id=1,
            is_favorite=True,
            current_user=mock_current_user,
            db=mock_db,
        )

        call_args = mock_service.update_saved_property.call_args
        assert call_args.kwargs["updates"] == {"is_favorite": True}


class TestBulkOperations:
    """Tests for bulk operations."""

    @pytest.mark.asyncio
    async def test_bulk_archive_success(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test bulk archive."""

        mock_service = mock_saved_property_service.return_value
        mock_service.bulk_update.return_value = 3

        result = await bulk_archive(
            saved_property_ids=[1, 2, 3],
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_bulk_delete_success(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test bulk delete."""

        mock_service = mock_saved_property_service.return_value
        mock_service.bulk_delete.return_value = 2

        result = await bulk_delete(
            saved_property_ids=[1, 2],
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result is None


class TestMarkAsViewed:
    """Tests for mark_as_viewed endpoint."""

    @pytest.mark.asyncio
    async def test_mark_as_viewed_with_date(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_saved_property,
    ):
        """Test marking as viewed with custom date."""

        mock_service = mock_saved_property_service.return_value
        mock_service.update_saved_property.return_value = mock_saved_property

        await mark_as_viewed(
            saved_property_id=1,
            viewing_date="2024-01-15",
            current_user=mock_current_user,
            db=mock_db,
        )

        call_args = mock_service.update_saved_property.call_args
        assert call_args.kwargs["updates"]["viewed_in_person"] is True

    @pytest.mark.asyncio
    async def test_mark_as_viewed_invalid_date(
        self, mock_current_user, mock_db, mock_saved_property_service
    ):
        """Test marking as viewed with invalid date."""

        with pytest.raises(HTTPException) as exc_info:
            await mark_as_viewed(
                saved_property_id=1,
                viewing_date="invalid-date",
                current_user=mock_current_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestGetPropertiesForComparison:
    """Tests for get_properties_for_comparison endpoint."""

    @pytest.mark.asyncio
    async def test_get_properties_for_comparison_success(
        self,
        mock_current_user,
        mock_db,
        mock_saved_property_service,
        mock_saved_property,
    ):
        """Test successful property comparison."""

        mock_service = mock_saved_property_service.return_value
        mock_service.get_saved_property_by_id.return_value = mock_saved_property

        result = await get_properties_for_comparison(
            saved_property_ids="1,2,3",
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_get_properties_for_comparison_too_many(self, mock_current_user, mock_db):
        """Test comparison with too many properties."""

        with pytest.raises(HTTPException) as exc_info:
            await get_properties_for_comparison(
                saved_property_ids="1,2,3,4,5,6",
                current_user=mock_current_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
