# PlaceResearch

A tool for researching places by gathering data from multiple providers including flood zones, walk/bike scores, and railroad proximity.

## Features

- **Multi-provider data gathering**: Collect data from flood zone APIs, WalkScore, and railroad datasets
- **Configurable providers**: Enable/disable specific data providers through configuration
- **Command-line interface**: Easy-to-use CLI for research and cache management

## Installation

```bash
uv sync
```

## Usage

### Start the API

```bash
research serve --port 8000
```

## Environment Variables

Create a `.env` file with the following variables:

```env
GOOGLE_MAPS_MAP_ID=
GOOGLE_MAPS_API_KEY=
NATIONAL_FLOOD_DATA_API_KEY=
NATIONAL_FLOOD_DATA_CLIENT_ID=
WALKSCORE_API_KEY=
AIRNOW_API_KEY=
FBI_API_KEY=
RAILLINES_PATH=
NOCODB_BASE_URL=
NOCODB_API_KEY=
NOCODB_TABLE_ID=
ANNUAL_CLIMATE_PATH=
DISTANCE_CONFIG_PATH=
```

## Available Providers

1. **Flood Zone Provider**: FEMA flood zone data
2. **Walk/Bike Score Provider**: Walkability and bikeability scores
3. **Railroad Provider**: Distance to nearest railroad lines
4. **Air Quality Provider**: Air quality index data
5. **Walmart Proximity Provider**: Distance to nearest Walmart stores
6. **Distances Provider**: Distance to specified addresses
7. **Annual Climate Provider**: Climate data from annual summaries

## Development

Install development dependencies:

```bash
uv sync --dev
```

Run tests:

```bash
uv run pytest
```
