"""Interfaces"""

from typing import Protocol, runtime_checkable


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
    """Protocol for place providers."""

    @property
    def name(self) -> str:
        ...

    def fetch_place_data(self, place: Place):
        ...
