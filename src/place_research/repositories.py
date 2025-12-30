"""Repository implementations for place persistence.

This module provides concrete implementations of the PlaceRepository protocol:
- InMemoryRepository: For testing and development
- NocoDBRepository: For production use with NocoDB
"""

import logging
from typing import Optional, Any

from .models import Place
from .clients.nocodb import NocoDBClient


class InMemoryRepository:
    """In-memory repository for testing and development.

    Stores places in a dictionary keyed by ID. Not thread-safe.
    """

    def __init__(self):
        self._places: dict[str, Place] = {}
        self._next_id = 1
        self.logger = logging.getLogger(__name__)

    def get_all(self) -> list[Place]:
        """Return all places."""
        return list(self._places.values())

    def get_by_id(self, place_id: str) -> Optional[Place]:
        """Get a place by ID."""
        return self._places.get(place_id)

    def save(self, place: Place) -> Place:
        """Save a place. Assigns ID if not present."""
        if not place.id:
            place.id = str(self._next_id)
            self._next_id += 1

        self._places[place.id] = place
        self.logger.debug("Saved place %s", place.id)
        return place

    def delete(self, place_id: str) -> bool:
        """Delete a place by ID."""
        if place_id in self._places:
            del self._places[place_id]
            self.logger.debug("Deleted place %s", place_id)
            return True
        return False

    def query(self, filters: dict[str, Any]) -> list[Place]:
        """Query places with simple equality filters."""
        results = []
        for place in self._places.values():
            match = True
            for key, value in filters.items():
                if not hasattr(place, key) or getattr(place, key) != value:
                    match = False
                    break
            if match:
                results.append(place)
        return results

    def clear(self) -> None:
        """Clear all places (useful for testing)."""
        self._places.clear()
        self._next_id = 1


class NocoDBRepository:
    """NocoDB-backed repository for production use.

    Wraps the existing NocoDB client to implement the PlaceRepository protocol.
    """

    def __init__(self, client: NocoDBClient):
        """Initialize with a NocoDB client.

        Args:
            client: Configured NocoDB instance
        """
        self.client = client
        self.logger = logging.getLogger(__name__)

    def get_all(self) -> list[Place]:
        """Fetch all places from NocoDB."""
        self.logger.info("Fetching all places from NocoDB")
        records = self.client.get_all_records()
        places = [Place(**record) for record in records]
        self.logger.info("Fetched %d places", len(places))
        return places

    def get_by_id(self, place_id: str) -> Optional[Place]:
        """Fetch a single place by ID from NocoDB.

        Note: This implementation fetches all and filters. Could be optimized
        with NocoDB query API if performance is an issue.
        """
        places = self.get_all()
        for place in places:
            if place.id == place_id:
                return place
        return None

    def save(self, place: Place) -> Place:
        """Save a place to NocoDB.

        If place has an ID, updates existing record. Otherwise creates new.
        """
        if place.id:
            self.logger.info(f"Updating place {place.id} in NocoDB")
            # Use the update method if it exists, otherwise use upsert logic
            self.client.update_record(place.id, place.model_dump(by_alias=True))
        else:
            self.logger.info("Creating new place in NocoDB")
            # NocoDB create logic would go here
            # For now, just update since we don't have create method
            raise NotImplementedError("Creating new places not yet implemented")

        return place

    def delete(self, place_id: str) -> bool:
        """Delete a place from NocoDB.

        Note: Requires implementing delete in NocoDBClient.
        """
        raise NotImplementedError("Delete not yet implemented in NocoDBClient")

    def query(self, filters: dict[str, Any]) -> list[Place]:
        """Query places with filters.

        Note: Simple in-memory filtering. Could be optimized with NocoDB filters.
        """
        places = self.get_all()
        results = []
        for place in places:
            match = True
            for key, value in filters.items():
                if not hasattr(place, key) or getattr(place, key) != value:
                    match = False
                    break
            if match:
                results.append(place)
        return results
