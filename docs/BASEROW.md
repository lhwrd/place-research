# Baserow integration

Baserow (`https://place-research-baserow.snake-snares.ts.net`, database 259) is the UI
and the only data store. The backend has no database. It creates rows for listings
shared from the iOS Shortcut, and enriches rows when Baserow's webhook tells it to.

```
iOS Shortcut ─POST /api/v1/listings {url, listing_json}────▶ backend ─create row (Status=New)──▶ Baserow
iOS Shortcut ─POST /api/v1/listings/{row_id}/images──────▶ backend ─upload + append Photos──▶ Baserow
Baserow ─webhook rows.created / rows.updated─▶ POST /api/v1/webhooks/baserow
   backend (background): Status=Enriching → geocode → run providers → write fields, Status=Enriched
                         (Status=Error and the message in Error if anything fails)
```

## Status

| Status      | Meaning                                                              |
| ----------- | -------------------------------------------------------------------- |
| *(empty)*   | Added by hand in Baserow; treated like New                           |
| `New`       | Created by the Shortcut; enrichment is queued                        |
| `Enriching` | In progress                                                          |
| `Enriched`  | Done; see Last enriched                                              |
| `Error`     | Failed; see the Error field                                          |
| `Re-enrich` | Set this yourself to run enrichment again, bypassing the cache       |

Only empty, `New` and `Re-enrich` rows are enriched. The backend's own Status updates
fire `rows.updated` webhooks too, but those rows are `Enriching`, `Enriched` or `Error`,
so they're ignored. A sweep on startup and every 15 minutes
(`BASEROW_SWEEP_INTERVAL_SECONDS`) picks up rows whose webhook was missed.

## Tables

All field names are defined in `app/integrations/baserow_schema.py`.

- **Properties (837)**
  - Listing: Address, Zillow URL, Zillow ID, Status, Error, Photos, Listing JSON, Price,
    Beds, Baths, Sqft, Lot (acres), Year built, Property type, Latitude, Longitude.
  - Enrichment: Walk, Bike and Transit score, Flood zone, Rail distance (mi), Highway
    distance (mi), Road noise, Avg temp, Avg precip, Air quality, Drive times,
    Nearby places, Last enriched.
  - **Yours (never written by the backend):** Notes, Rating, Visited.
- **Locations**: drive-time destinations. Name, Address, Type (Family / Friend / Work /
  Other), Active, Priority. Only Active rows are used, highest Priority first.
- **Settings**: a single row. Amenity types (Google Places types, e.g. `grocery_store`)
  and Preferred places (free-text searches, e.g. `Costco`), one per line.

A failed provider never blanks a field: only providers that return data are written.

## Setup

1. **Database token.** In Baserow: *My settings → Database tokens*. Give it create,
   read and update on database 259 and set it as `BASEROW_API_TOKEN`.
2. **Schema.** From the repo root, run:

   ```bash
   uv run python scripts/baserow_setup.py --webhook-url https://<backend-host>/api/v1/webhooks/baserow
   ```

   It signs in as you (database tokens can't change schema) and creates only what's
   missing: the Properties fields, the Locations and Settings tables, the Settings row
   and the webhook (with the `X-Webhook-Secret` header from `BASEROW_WEBHOOK_SECRET`).
   Put the table ids it prints into `BASEROW_LOCATIONS_TABLE_ID` and
   `BASEROW_SETTINGS_TABLE_ID`. Safe to re-run.
3. **Baserow host settings** (managed outside this repo):
   - Set `BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS=true`. Tailnet addresses are in
     100.64.0.0/10, which Baserow blocks for webhooks by default.
   - The Baserow container must be able to resolve and reach the backend's tailnet
     name. Docker containers often don't use MagicDNS; if the name doesn't resolve
     from inside the container, use the backend's tailnet IP in the webhook URL.

## iOS Shortcut API

Both endpoints need `Authorization: Bearer <INGEST_API_TOKEN>`. The phone must be on
the tailnet.

### Add a listing

```
POST /api/v1/listings
Content-Type: application/json

{"url": "https://www.zillow.com/homedetails/.../46284123_zpid/",
 "listing_json": { ...anything extracted from the page... }}
```

Response: `{"row_id": 12, "created": true}`. Sharing the same listing again (same
zpid) returns the existing row with `"created": false`.

`listing_json` is optional, as an object or a JSON string. The parser looks for
Zillow's embedded property object (from `__NEXT_DATA__`, including the
`gdpClientCache` JSON string) and schema.org JSON-LD blocks, and takes address,
price, beds, baths, sqft, lot, year built, type and coordinates from them. Without it,
the address comes from the URL slug and the geocoder does the rest.

### Add photos

```
POST /api/v1/listings/{row_id}/images
```

Either:

- `multipart/form-data` with one or more parts named `file` (up to 50 per request), or
- a raw image body with its `Content-Type` (e.g. `image/jpeg`), optionally
  `?filename=front`.

Each image may be up to 25 MB. Photos are appended to the row's Photos field.
Response: `{"row_id": 12, "uploaded": 3, "photo_count": 7}`.

### curl

```bash
curl -s -X POST "$API/api/v1/listings" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"url": "https://www.zillow.com/homedetails/x/46284123_zpid/"}'

curl -s -X POST "$API/api/v1/listings/12/images" -H "Authorization: Bearer $TOKEN" \
  -F file=@front.jpg -F file=@kitchen.jpg
```
