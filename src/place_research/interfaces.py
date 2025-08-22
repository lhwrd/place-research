# interfaces.py
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .models import City, County, Place, State

if TYPE_CHECKING:
    from .config import Config


@runtime_checkable
class BaseProvider(Protocol):
    """Base provider interface that all providers should implement."""

    def __init__(self, config: "Config | None" = None): ...


@runtime_checkable
class PlaceProvider(Protocol):
    def fetch_place_data(self, place: Place): ...


@runtime_checkable
class CityProvider(Protocol):
    def fetch_city_data(self, city: City): ...


@runtime_checkable
class CountyProvider(Protocol):
    def fetch_county_data(self, county: County): ...


@runtime_checkable
class StateProvider(Protocol):
    def fetch_state_data(self, state: State): ...
