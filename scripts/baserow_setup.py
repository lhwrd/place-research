"""Create the Baserow tables, fields and webhook the backend expects.

Database tokens can't change schema, so this signs in as you (JWT). It only adds what's
missing, matched by name, and never deletes or retypes anything, so it's safe to re-run.

Usage (from the repo root):
    uv run python scripts/baserow_setup.py \\
        --webhook-url https://<backend>.snake-snares.ts.net/api/v1/webhooks/baserow

Defaults for the URL, database id, Properties table id and webhook secret come from
BASEROW_* settings (.env). BASEROW_EMAIL is used if set; the password is always prompted.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.integrations.baserow_schema import (  # noqa: E402
    LOCATION_FIELD_DEFS,
    PROPERTY_FIELD_DEFS,
    SETTINGS_FIELD_DEFS,
    LocationFields,
    PropertyFields,
    SettingsFields,
)

WEBHOOK_NAME = "place-research enrichment"
WEBHOOK_EVENTS = ["rows.created", "rows.updated"]


class BaserowAdmin:
    """Minimal JWT-authenticated client for Baserow's schema endpoints."""

    def __init__(self, base_url: str, email: str, password: str):
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=30)
        response = self.http.post(
            "/api/user/token-auth/", json={"email": email, "password": password}
        )
        self._check(response)
        body = response.json()
        self.http.headers["Authorization"] = f"JWT {body.get('access_token') or body['token']}"

    def get(self, path: str) -> Any:
        return self._check(self.http.get(path)).json()

    def post(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._check(self.http.post(path, json=payload)).json()

    def patch(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._check(self.http.patch(path, json=payload)).json()

    @staticmethod
    def _check(response: httpx.Response) -> httpx.Response:
        if response.is_error:
            sys.exit(
                f"Baserow {response.request.method} {response.request.url.path} failed: "
                f"{response.status_code} {response.text}"
            )
        return response


def ensure_table(admin: BaserowAdmin, database_id: int, name: str, primary: str) -> int:
    """Return the id of the named table, creating it (primary field only, no rows) if needed."""
    for table in admin.get(f"/api/database/tables/database/{database_id}/"):
        if table["name"] == name:
            print(f"  table {name!r} exists (id {table['id']})")
            return table["id"]
    # A one-cell header row gives a table with just the primary field and no sample rows
    table = admin.post(
        f"/api/database/tables/database/{database_id}/",
        {"name": name, "data": [[primary]], "first_row_header": True},
    )
    print(f"  created table {name!r} (id {table['id']})")
    return table["id"]


def ensure_fields(
    admin: BaserowAdmin, table_id: int, primary: str, definitions: List[Dict[str, Any]]
) -> None:
    fields = admin.get(f"/api/database/fields/table/{table_id}/")
    by_name = {f["name"]: f for f in fields}

    primary_field = next(f for f in fields if f.get("primary"))
    if primary_field["name"] != primary:
        admin.patch(f"/api/database/fields/{primary_field['id']}/", {"name": primary})
        print(f"  renamed primary field {primary_field['name']!r} -> {primary!r}")

    for definition in definitions:
        existing = by_name.get(definition["name"])
        if existing is None:
            admin.post(f"/api/database/fields/table/{table_id}/", definition)
            print(f"  + {definition['name']} ({definition['type']})")
        elif existing["type"] != definition["type"]:
            print(
                f"  ! {definition['name']} is {existing['type']}, expected {definition['type']} "
                "(left unchanged; fix it in Baserow)"
            )


def ensure_settings_row(admin: BaserowAdmin, table_id: int) -> None:
    rows = admin.get(f"/api/database/rows/table/{table_id}/?user_field_names=true")
    if rows["count"] == 0:
        admin.post(
            f"/api/database/rows/table/{table_id}/?user_field_names=true",
            {SettingsFields.NAME: "Default"},
        )
        print("  created the Settings row")


def ensure_webhook(admin: BaserowAdmin, table_id: int, url: str, secret: str) -> None:
    for webhook in admin.get(f"/api/database/webhooks/table/{table_id}/"):
        if webhook["url"] == url:
            print(f"  webhook to {url} exists (id {webhook['id']})")
            return
    admin.post(
        f"/api/database/webhooks/table/{table_id}/",
        {
            "name": WEBHOOK_NAME,
            "url": url,
            "request_method": "POST",
            "include_all_events": False,
            "events": WEBHOOK_EVENTS,
            "use_user_field_names": True,
            "headers": {"X-Webhook-Secret": secret},
        },
    )
    print(f"  created webhook -> {url}")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default=settings.baserow_url)
    parser.add_argument("--database-id", type=int, default=settings.baserow_database_id)
    parser.add_argument(
        "--properties-table-id", type=int, default=settings.baserow_properties_table_id
    )
    parser.add_argument("--webhook-url", help="Backend webhook URL; skipped if omitted")
    parser.add_argument("--webhook-secret", default=settings.baserow_webhook_secret)
    args = parser.parse_args(argv)

    if not (args.url and args.database_id and args.properties_table_id):
        parser.error(
            "--url, --database-id and --properties-table-id are required (or set BASEROW_*)"
        )
    if args.webhook_url and not args.webhook_secret:
        parser.error("--webhook-url needs --webhook-secret (or BASEROW_WEBHOOK_SECRET)")

    email = os.environ.get("BASEROW_EMAIL") or input("Baserow email: ")
    admin = BaserowAdmin(args.url, email, getpass.getpass("Baserow password: "))

    print(f"Properties (table {args.properties_table_id})")
    ensure_fields(admin, args.properties_table_id, PropertyFields.ADDRESS, PROPERTY_FIELD_DEFS)

    print("Locations")
    locations_id = ensure_table(admin, args.database_id, "Locations", LocationFields.NAME)
    ensure_fields(admin, locations_id, LocationFields.NAME, LOCATION_FIELD_DEFS)

    print("Settings")
    settings_id = ensure_table(admin, args.database_id, "Settings", SettingsFields.NAME)
    ensure_fields(admin, settings_id, SettingsFields.NAME, SETTINGS_FIELD_DEFS)
    ensure_settings_row(admin, settings_id)

    if args.webhook_url:
        print("Webhook")
        ensure_webhook(admin, args.properties_table_id, args.webhook_url, args.webhook_secret)

    print("\nAdd to the backend environment:")
    print(f"BASEROW_PROPERTIES_TABLE_ID={args.properties_table_id}")
    print(f"BASEROW_LOCATIONS_TABLE_ID={locations_id}")
    print(f"BASEROW_SETTINGS_TABLE_ID={settings_id}")


if __name__ == "__main__":
    main()
