from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.cache_entry import CacheEntry
from app.services.cache_service import CacheService

"""Tests for cache service."""


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.query = Mock()
    db.commit = Mock()
    db.add = Mock()
    db.delete = Mock()
    db.func = Mock()
    return db


@pytest.fixture
def cache_service(mock_db):
    """Cache service instance with mocked database."""
    # Patch the settings to enable cache for tests
    with patch("app.services.cache_service.get_settings") as mock_settings:
        mock_settings.return_value.cache_enabled = True
        service = CacheService(mock_db)
        yield service


class TestGet:
    """Tests for get method."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_default(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None

        result = await cache_service.get("missing_key", default="default_value")

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_cache_hit_returns_value(self, cache_service, mock_db):
        mock_entry = Mock(spec=CacheEntry)
        mock_entry.value = '{"data": "test"}'
        mock_entry.expires_at = None
        mock_entry.access_count = 0
        mock_db.query().filter().first.return_value = mock_entry

        result = await cache_service.get("test_key")

        assert result == {"data": "test"}
        assert mock_entry.access_count == 1
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_entry_returns_default(self, cache_service, mock_db):
        mock_entry = Mock(spec=CacheEntry)
        mock_entry.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_db.query().filter().first.return_value = mock_entry

        result = await cache_service.get("expired_key", default=None)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_entry)


class TestSet:
    """Tests for set method."""

    @pytest.mark.asyncio
    async def test_set_new_entry(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None

        await cache_service.set("new_key", {"data": "value"}, ttl_seconds=3600)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_updates_existing_entry(self, cache_service, mock_db):
        mock_entry = Mock(spec=CacheEntry)
        mock_db.query().filter().first.return_value = mock_entry

        await cache_service.set("existing_key", {"data": "new_value"}, ttl_days=7)

        assert mock_entry.value == '{"data": "new_value"}'
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_with_ttl_seconds(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None

        await cache_service.set("test_key", "value", ttl_seconds=3600)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.expires_at is not None

    @pytest.mark.asyncio
    async def test_set_with_ttl_days(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None

        await cache_service.set("test_key", "value", ttl_days=7)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.expires_at is not None


class TestDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_existing_entry(self, cache_service, mock_db):
        mock_entry = Mock(spec=CacheEntry)
        mock_db.query().filter().first.return_value = mock_entry

        result = await cache_service.delete("test_key")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_entry)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_missing_entry(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None

        result = await cache_service.delete("missing_key")

        assert result is False
        mock_db.delete.assert_not_called()


class TestExists:
    """Tests for exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_valid_entry(self, cache_service, mock_db):
        mock_entry = Mock(spec=CacheEntry)
        mock_entry.expires_at = None
        mock_db.query().filter().first.return_value = mock_entry

        result = await cache_service.exists("test_key")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing_entry(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None

        result = await cache_service.exists("missing_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_expired_entry(self, cache_service, mock_db):
        mock_entry = Mock(spec=CacheEntry)
        mock_entry.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_db.query().filter().first.return_value = mock_entry

        result = await cache_service.exists("expired_key")

        assert result is False


class TestGetMany:
    """Tests for get_many method."""

    @pytest.mark.asyncio
    async def test_get_many_returns_found_keys(self, cache_service, mock_db):
        mock_entry1 = Mock(spec=CacheEntry)
        mock_entry1.value = '"value1"'
        mock_entry1.expires_at = None
        mock_entry1.access_count = 0

        mock_db.query().filter().first.side_effect = [mock_entry1, None]

        result = await cache_service.get_many(["key1", "key2"])

        assert result == {"key1": "value1"}


class TestSetMany:
    """Tests for set_many method."""

    @pytest.mark.asyncio
    async def test_set_many_sets_all_items(self, cache_service, mock_db):
        mock_db.query().filter().first.return_value = None
        items = {"key1": "value1", "key2": "value2"}

        await cache_service.set_many(items, ttl_seconds=3600)

        assert mock_db.add.call_count == 2


class TestClearExpired:
    """Tests for clear_expired method."""

    @pytest.mark.asyncio
    async def test_clear_expired_removes_expired_entries(self, cache_service, mock_db):
        mock_query = Mock()
        mock_query.filter().delete.return_value = 5
        mock_db.query.return_value = mock_query

        result = await cache_service.clear_expired()

        assert result == 5
        mock_db.commit.assert_called_once()


class TestClearAll:
    """Tests for clear_all method."""

    @pytest.mark.asyncio
    async def test_clear_all_removes_all_entries(self, cache_service, mock_db):
        mock_query = Mock()
        mock_query.delete.return_value = 10
        mock_db.query.return_value = mock_query

        result = await cache_service.clear_all()

        assert result == 10
        mock_db.commit.assert_called_once()


class TestGenerateKey:
    """Tests for generate_key method."""

    def test_generate_key_with_args(self, cache_service):
        key1 = cache_service.generate_key("property", "123")
        key2 = cache_service.generate_key("property", "123")

        assert key1 == key2

    def test_generate_key_with_kwargs(self, cache_service):
        key1 = cache_service.generate_key(lat=47.6062, lon=-122.3321)
        key2 = cache_service.generate_key(lat=47.6062, lon=-122.3321)

        assert key1 == key2

    def test_generate_key_different_args_different_hash(self, cache_service):
        key1 = cache_service.generate_key("property", "123")
        key2 = cache_service.generate_key("property", "456")

        assert key1 != key2


class TestSerializeDeserialize:
    """Tests for serialization methods."""

    def test_serialize_valid_value(self, cache_service):
        value = {"data": "test"}
        serialized = cache_service._serialize(value)

        assert serialized == '{"data": "test"}'

    def test_serialize_invalid_value_raises_error(self, cache_service):
        with pytest.raises(ValueError):
            cache_service._serialize(Mock())

    def test_deserialize_valid_json(self, cache_service):
        serialized = '{"data": "test"}'
        value = cache_service._deserialize(serialized)

        assert value == {"data": "test"}

    def test_deserialize_invalid_json_returns_none(self, cache_service):
        value = cache_service._deserialize("invalid json")

        assert value is None


class TestCacheDisabled:
    """Tests for cache service when caching is disabled."""

    @pytest.mark.asyncio
    async def test_get_returns_default_when_cache_disabled(self, mock_db):
        """Test that get returns default when cache is disabled."""
        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value.cache_enabled = False
            service = CacheService(mock_db)

            result = await service.get("test_key", default="default")

            assert result == "default"
            # Should not query database
            mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_skips_when_cache_disabled(self, mock_db):
        """Test that set is skipped when cache is disabled."""
        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value.cache_enabled = False
            service = CacheService(mock_db)

            await service.set("test_key", "test_value")

            # Should not interact with database
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_cache_disabled(self, mock_db):
        """Test that delete returns False when cache is disabled."""
        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value.cache_enabled = False
            service = CacheService(mock_db)

            result = await service.delete("test_key")

            assert result is False
            # Should not query database
            mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_cache_disabled(self, mock_db):
        """Test that exists returns False when cache is disabled."""
        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value.cache_enabled = False
            service = CacheService(mock_db)

            result = await service.exists("test_key")

            assert result is False
            # Should not query database
            mock_db.query.assert_not_called()
