"""In-memory stand-in for BaserowAPI, shared by service and endpoint tests."""

import itertools
from typing import Any, Dict, List, Optional

from app.exceptions import ExternalAPIError
from app.integrations.baserow_schema import PropertyFields, Status

STATUS_OPTION_IDS = {value: 100 + i for i, value in enumerate(Status.ALL)}


class FakeBaserowAPI:
    """Stores rows per table and mimics the parts of Baserow's API the app uses.

    Single selects are written as option ids and read back as {"id", "value"} dicts,
    like the real API.
    """

    def __init__(self):
        self.tables: Dict[int, Dict[int, Dict[str, Any]]] = {}
        self.uploads: List[Dict[str, Any]] = []
        self.updates: List[tuple] = []
        self._ids = itertools.count(1)

    def add_row(self, table_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
        row = {"id": next(self._ids), **values}
        self.tables.setdefault(table_id, {})[row["id"]] = row
        return row

    def row(self, table_id: int, row_id: int) -> Dict[str, Any]:
        return self.tables[table_id][row_id]

    async def select_option_id(self, table_id: int, field_name: str, value: str) -> int:
        return STATUS_OPTION_IDS[value]

    async def list_rows(
        self,
        table_id: int,
        equals: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        rows = list(self.tables.get(table_id, {}).values())
        for name, value in (equals or {}).items():
            rows = [r for r in rows if r.get(name) == value]
        return [dict(r) for r in rows]

    async def get_row(self, table_id: int, row_id: int) -> Dict[str, Any]:
        row = self.tables.get(table_id, {}).get(row_id)
        if row is None:
            raise ExternalAPIError(service="baserow", message="missing", api_status_code=404)
        return dict(row)

    async def create_row(self, table_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
        return self.add_row(table_id, self._decode(values))

    async def update_row(self, table_id: int, row_id: int, values: Dict[str, Any]):
        self.updates.append((row_id, dict(values)))
        self.tables[table_id][row_id].update(self._decode(values))
        return self.tables[table_id][row_id]

    async def upload_file(self, content: bytes, filename: str, content_type: str):
        uploaded = {"name": f"stored_{len(self.uploads)}_{filename}", "size": len(content)}
        self.uploads.append(uploaded)
        return uploaded

    @staticmethod
    def _decode(values: Dict[str, Any]) -> Dict[str, Any]:
        decoded = dict(values)
        status = decoded.get(PropertyFields.STATUS)
        if isinstance(status, int):
            label = next(k for k, v in STATUS_OPTION_IDS.items() if v == status)
            decoded[PropertyFields.STATUS] = {"id": status, "value": label}
        return decoded
