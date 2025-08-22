from typing import Any

class State:
    def __init__(self, name: str, abbreviation: str):
        self.name = name
        self.abbreviation = abbreviation
        self.attributes: dict[str, Any] = {}