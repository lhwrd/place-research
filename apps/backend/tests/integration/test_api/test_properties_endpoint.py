from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.properties import (
    delete_property,
    enrich_property,
    get_property,
    search_property,
)
from app.schemas.property import PropertySearchRequest


@pytest.fixture
def mock_db():
    """Mock database session"""
    return MagicMock()


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    user = MagicMock()
    user.id = 1
    return user


@pytest.fixture
def mock_property_data():
    """Mock property data"""
    from datetime import datetime

    return {
        "id": 1,
        "address": "123 Main St, Seattle, WA 98101",
        "city": "Seattle",
        "state": "WA",
        "zip_code": "98101",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "bedrooms": 3,
        "bathrooms": 2.0,
        "square_feet": 2000,
        "year_built": 2010,
        "property_type": "Single Family",
        "estimated_value": 750000,
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
        "updated_at": datetime(2024, 1, 1, 12, 0, 0),
    }


@pytest.fixture
def mock_enrichment_data():
    """Mock enrichment data"""
    from datetime import datetime

    return {
        "success": True,
        "enrichment_data": {
            "walk_score": {
                "data": {"walk_score": 85, "bike_score": 75},
                "success": True,
                "cached": False,
                "enriched_at": datetime(2024, 1, 1, 12, 0, 0),
                "error": None,
            }
        },
        "metadata": {
            "total_providers": 1,
            "successful_providers": 1,
            "failed_providers": 0,
            "total_api_calls": 1,
            "cached_providers": 0,
        },
    }


class TestSearchProperty:
    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_search_property_success(
        self, mock_service_class, mock_db, mock_current_user, mock_property_data
    ):
        """Test successful property search"""
        mock_service = AsyncMock()
        mock_service.search_by_address.return_value = mock_property_data
        mock_service_class.return_value = mock_service

        request = PropertySearchRequest(address="123 Main St, Seattle, WA 98101")
        response = await search_property(request, mock_db, mock_current_user)

        assert response.success is True
        assert response.property.model_dump() == mock_property_data
        assert response.message == "Property found successfully"
        mock_service.search_by_address.assert_called_once_with(
            address=request.address, user_id=mock_current_user.id
        )

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_search_property_not_found(self, mock_service_class, mock_db, mock_current_user):
        """Test property search when property not found"""
        mock_service = AsyncMock()
        mock_service.search_by_address.return_value = None
        mock_service_class.return_value = mock_service

        request = PropertySearchRequest(address="123 Main St, Seattle, WA 98101")

        with pytest.raises(HTTPException) as exc_info:
            await search_property(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_search_property_value_error(
        self, mock_service_class, mock_db, mock_current_user
    ):
        """Test property search with invalid input"""
        mock_service = AsyncMock()
        mock_service.search_by_address.side_effect = ValueError("Invalid address format")
        mock_service_class.return_value = mock_service

        request = PropertySearchRequest(address="invalid")

        with pytest.raises(HTTPException) as exc_info:
            await search_property(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestEnrichProperty:
    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.EnrichmentOrchestrator")
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_enrich_property_success(
        self,
        mock_service_class,
        mock_orchestrator_class,
        mock_db,
        mock_current_user,
        mock_property_data,
        mock_enrichment_data,
    ):
        """Test successful property enrichment"""
        mock_service = AsyncMock()
        mock_service.get_property_by_id.return_value = mock_property_data
        mock_service_class.return_value = mock_service

        mock_orchestrator = AsyncMock()
        mock_orchestrator.enrich_property.return_value = mock_enrichment_data
        mock_orchestrator_class.return_value = mock_orchestrator

        response = await enrich_property(1, True, mock_db, mock_current_user)

        assert response.success is True
        assert response.property_id == 1
        assert response.enrichment.model_dump() == mock_enrichment_data
        mock_orchestrator.enrich_property.assert_called_once_with(
            property_id=1, user_id=mock_current_user.id, use_cached=True
        )

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_enrich_property_not_found(self, mock_service_class, mock_db, mock_current_user):
        """Test enrichment when property not found"""
        mock_service = AsyncMock()
        mock_service.get_property_by_id.return_value = None
        mock_service_class.return_value = mock_service

        with pytest.raises(HTTPException) as exc_info:
            await enrich_property(999, True, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestGetProperty:
    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_get_property_success(
        self, mock_service_class, mock_db, mock_current_user, mock_property_data
    ):
        """Test successful property retrieval"""
        mock_service = AsyncMock()
        mock_service.get_property_by_id.return_value = mock_property_data
        mock_service_class.return_value = mock_service

        response = await get_property(1, mock_db, mock_current_user)

        assert response.success is True
        assert response.property.model_dump() == mock_property_data

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_get_property_not_found(self, mock_service_class, mock_db, mock_current_user):
        """Test property retrieval when not found"""
        mock_service = AsyncMock()
        mock_service.get_property_by_id.return_value = None
        mock_service_class.return_value = mock_service

        with pytest.raises(HTTPException) as exc_info:
            await get_property(999, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteProperty:
    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_delete_property_success(self, mock_service_class, mock_db, mock_current_user):
        """Test successful property deletion"""
        mock_service = AsyncMock()
        mock_service.delete_property.return_value = True
        mock_service_class.return_value = mock_service

        response = await delete_property(1, mock_db, mock_current_user)

        assert response is None
        mock_service.delete_property.assert_called_once_with(
            property_id=1, user_id=mock_current_user.id
        )

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.properties.PropertyService")
    async def test_delete_property_not_found(self, mock_service_class, mock_db, mock_current_user):
        """Test property deletion when not found"""
        mock_service = AsyncMock()
        mock_service.delete_property.return_value = False
        mock_service_class.return_value = mock_service

        with pytest.raises(HTTPException) as exc_info:
            await delete_property(999, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
