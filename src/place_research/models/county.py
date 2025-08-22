from typing import Any


class County:
    def __init__(self, name: str, state: str):
        self.name = name
        self.state = state
        self.attributes: dict[str, Any] = {}
