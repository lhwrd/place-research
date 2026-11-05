"""Baserow REST API client (rows and file uploads, authenticated with a database token)."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.exceptions import APIKeyInvalidError, ExternalAPIError
from app.integrations.base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class BaserowAPI(BaseAPIClient):
    """
    Client for Baserow's database row API.

    Database tokens only cover rows and file uploads; schema changes (fields,
    tables, webhooks) need a user JWT and live in scripts/baserow_setup.py.
    All row calls use user_field_names, so rows are keyed by field name.
    """

    PAGE_SIZE = 200

    def __init__(self, base_url: Optional[str] = None, api_token: Optional[str] = None):
        super().__init__(
            base_url=base_url or settings.baserow_url or "",
            api_key=api_token or settings.baserow_api_token,
            timeout=30,
            rate_limit_per_second=None,
        )
        self._fields: Dict[int, Dict[str, Dict[str, Any]]] = {}

    def _get_service_name(self) -> str:
        """Return service name."""
        return "baserow"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Token {self.api_key}"}

    async def _handle_http_error(self, error: httpx.HTTPStatusError):
        """Baserow errors look like {"error": "ERROR_CODE", "detail": ...}."""
        status_code = error.response.status_code
        try:
            body = error.response.json()
            message = f"{body.get('error')}: {body.get('detail')}"
        except ValueError:
            message = error.response.text or str(error)

        logger.error(
            "Baserow API HTTP error: %d - %s",
            status_code,
            message,
            extra={"service": "baserow", "status_code": status_code, "error_message": message},
        )
        if status_code in (401, 403):
            raise APIKeyInvalidError(service="baserow")
        raise ExternalAPIError(service="baserow", message=message, api_status_code=status_code)

    async def validate_api_key(self) -> bool:
        """Check the token by reading the Properties table's fields."""
        if not self.api_key or not settings.baserow_properties_table_id:
            return False
        try:
            await self.get_fields(settings.baserow_properties_table_id, refresh=True)
            return True
        except (APIKeyInvalidError, ExternalAPIError):
            return False

    # Fields

    async def get_fields(self, table_id: int, refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """Return the table's fields keyed by name (cached per client)."""
        if refresh or table_id not in self._fields:
            fields = await self._make_request("GET", f"api/database/fields/table/{table_id}/")
            self._fields[table_id] = {f["name"]: f for f in fields}
        return self._fields[table_id]

    async def select_option_id(self, table_id: int, field_name: str, value: str) -> int:
        """Resolve a single-select option's id from its label."""
        field = (await self.get_fields(table_id)).get(field_name)
        if not field:
            raise ValueError(f"Field {field_name!r} not found in Baserow table {table_id}")
        for option in field.get("select_options", []):
            if option["value"] == value:
                return option["id"]
        raise ValueError(f"Option {value!r} not found in field {field_name!r}")

    # Rows

    async def list_rows(
        self,
        table_id: int,
        equals: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all rows in a table, following pagination.

        Args:
            table_id: Baserow table id
            equals: Optional {field name: value} filters, ANDed together
            include: Optional field names to return (defaults to all)
        """
        params: Dict[str, Any] = {"user_field_names": "true", "size": self.PAGE_SIZE}
        if include:
            params["include"] = ",".join(include)
        if equals:
            fields = await self.get_fields(table_id)
            for name, value in equals.items():
                params[f"filter__field_{fields[name]['id']}__equal"] = value

        rows: List[Dict[str, Any]] = []
        page = 1
        while True:
            data = await self._make_request(
                "GET", f"api/database/rows/table/{table_id}/", params={**params, "page": page}
            )
            rows.extend(data.get("results", []))
            if not data.get("next"):
                return rows
            page += 1

    async def get_row(self, table_id: int, row_id: int) -> Dict[str, Any]:
        """Fetch a single row."""
        return await self._make_request(
            "GET",
            f"api/database/rows/table/{table_id}/{row_id}/",
            params={"user_field_names": "true"},
        )

    async def create_row(self, table_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
        """Create a row."""
        return await self._make_request(
            "POST",
            f"api/database/rows/table/{table_id}/",
            params={"user_field_names": "true"},
            json_data=values,
        )

    async def update_row(
        self, table_id: int, row_id: int, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update only the given fields of a row."""
        return await self._make_request(
            "PATCH",
            f"api/database/rows/table/{table_id}/{row_id}/",
            params={"user_field_names": "true"},
            json_data=values,
        )

    # Files

    async def upload_file(self, content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Upload a file to Baserow's user-file storage.

        Returns the user-file object; attach it to a file field with {"name": result["name"]}.
        """
        url = f"{self.base_url}/api/user-files/upload-file/"
        try:
            response = await self.client.post(
                url,
                headers=self._get_auth_headers(),
                files={"file": (filename, content, content_type)},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.RequestError as e:
            raise ExternalAPIError(service="baserow", message=f"Upload failed: {e}") from e

        logger.info(
            "Uploaded file to Baserow: %s (%d bytes)",
            filename,
            len(content),
            extra={"service": "baserow", "upload_filename": filename, "size": len(content)},
        )
        return response.json()
