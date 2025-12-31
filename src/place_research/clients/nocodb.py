import json
import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger("nocodb")


@dataclass
class TableRecordsQuery:
    table_id: str
    fields: list[str] | None = None
    sort: list[str] | None = None
    where: dict | None = None
    offset: int | None = None
    limit: int | None = None
    view_id: str | None = None

    def as_dict(self):
        return {
            "table_id": self.table_id,
            "fields": self.fields,
            "sort": self.sort,
            "where": self.where,
            "offset": self.offset,
            "limit": self.limit,
            "view_id": self.view_id,
        }


class NocoDBClient:
    def __init__(
        self,
        base_url,
        api_key: str | None = None,
        timeout: int | None = None,
        verify_ssl: bool | None = None,
    ):
        logger.debug("Initializing NocoDB client")
        self.api_key = api_key or os.getenv("NOCODB_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required")
        self.base_url = base_url or os.getenv("NOCODB_BASE_URL")
        self.headers = {
            "xc-token": f"{self.api_key}",
            "Content-Type": "application/json",
        }
        self.timeout = timeout or 10
        self.verify_ssl = verify_ssl if verify_ssl is not None else True

    def list_table_records(self, table_query: TableRecordsQuery) -> dict:
        logger.debug("Listing records for table %s", table_query.table_id)
        url = f"{self.base_url}/tables/{table_query.table_id}/records"
        params = {
            "fields": table_query.fields,
            "sort": table_query.sort,
            "where": table_query.where,
            "offset": table_query.offset,
            "limit": table_query.limit,
            "viewId": table_query.view_id,
        }
        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        if response.status_code != 200:
            logger.error(response.json())

        response.raise_for_status()

        json_data = response.json()

        logger.debug(
            "Retrieved records for table %s: %s", table_query.table_id, json_data
        )

        return json_data

    def update_table_records(self, table_id: str, table_records: list[dict]):
        url = f"{self.base_url}/tables/{table_id}/records"
        response = requests.patch(
            url,
            headers=self.headers,
            json=table_records,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()

        json_data = response.json()
        logger.debug("Updated records for table %s: %s", table_id, json_data)

        return json_data

    def update_table_record(self, table_id: str, data: dict):
        logger.debug("Updating record in table %s", table_id)
        url = f"{self.base_url}/tables/{table_id}/records"
        # NocoDB expects a list of records for PATCH
        response = requests.patch(
            url,
            headers=self.headers,
            data=json.dumps(data),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        json_data = response.json()
        logger.debug("Updated record in table %s: %s", table_id, json_data)
        return json_data
