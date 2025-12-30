"""Interfaces and protocols for place-research.

This module defines the core abstractions:
- PlaceProvider: Protocol for data enrichment providers
- PlaceRepository: Protocol for data persistence
- DisplayableResult: Legacy base class for results
"""

from typing import Protocol, runtime_checkable, Optional, Any

from .models import Place


# Base class for displayable results (for polymorphic display logic)
class DisplayableResult:
    def display(self):
        """Display the result in a human-readable way."""
        raise NotImplementedError("Subclasses must implement display()")

    def to_dict(self):
        """Convert the result to a dictionary."""
        raise NotImplementedError("Subclasses must implement to_dict()")


class ProviderNameMixin:
    @property
    def name(self) -> str:
        return self.__class__.__name__.lower().replace("provider", "")


@runtime_checkable
class BaseProvider(Protocol):
    """Base provider interface that all providers should implement."""

    def __init__(self):
        ...


@runtime_checkable
class PlaceProvider(Protocol):
    """Protocol for place data enrichment providers.

    Providers fetch data from external sources and return structured results.
    They should NOT mutate Place objects directly (legacy providers still do this).

    Modern providers should:
    1. Accept configuration in __init__
    2. Return typed Result objects from fetch_place_data
    3. Handle errors gracefully (return None or raise specific exceptions)
    """

    @property
    def name(self) -> str:
        """Provider name for logging and error reporting."""
        ...

    def fetch_place_data(self, place: Place) -> Optional[Any]:
        """Fetch enrichment data for a place.

        Args:
            place: The place to enrich (read-only)

        Returns:
            A result object (e.g., WalkBikeScoreResult) or None if no data available.
            Legacy providers may mutate place and return None.
        """
        ...


@runtime_checkable
class PlaceRepository(Protocol):
    """Protocol for place data persistence.

    This abstraction allows swapping storage backends (NocoDB, PostgreSQL, in-memory, etc.)
    without changing business logic.
    """

    def get_all(self) -> list[Place]:
        """Fetch all places from the repository.

        Returns:
            List of all Place objects
        """
        ...

    def get_by_id(self, place_id: str) -> Optional[Place]:
        """Fetch a single place by ID.

        Args:
            place_id: The unique identifier for the place

        Returns:
            Place object if found, None otherwise
        """
        ...

    def save(self, place: Place) -> Place:
        """Save a place to the repository.

        Args:
            place: The place to save (create or update)

        Returns:
            The saved place (may have updated fields like ID)
        """
        ...

    def delete(self, place_id: str) -> bool:
        """Delete a place from the repository.

        Args:
            place_id: The ID of the place to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    def query(self, filters: dict[str, Any]) -> list[Place]:
        """Query places with filters.

        Args:
            filters: Dictionary of field names to values

        Returns:
            List of matching places
        """
        ...
