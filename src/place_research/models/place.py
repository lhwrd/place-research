from typing import Any

from .city import City
from .county import County
from .state import State


class Place:
    def __init__(self, address: str, coordinates: tuple[float, float]):
        self.address = address
        self.coordinates = coordinates
        self.city: City | None = None
        self.county: County | None = None
        self.state: State | None = None
        self.attributes: dict[str, Any] = {}