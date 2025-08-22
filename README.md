# PlaceResearch

A tool for researching places by gathering data from multiple providers including flood zones, walk/bike scores, and railroad proximity.

## Features

- **Multi-provider data gathering**: Collect data from flood zone APIs, WalkScore, and railroad datasets
- **Intelligent caching**: Automatic caching of API responses to reduce redundant calls and improve performance
- **Configurable providers**: Enable/disable specific data providers through configuration
- **Command-line interface**: Easy-to-use CLI for research and cache management

## Installation

```bash
uv sync
```

## Usage

### Basic Research

Research a place by address:

```bash
uv run research research "111 White Place, Port Orange, FL 32128"
```

### Cache Management

Check cache statistics:

```bash
uv run research cache-stats
```

Clear all cached data:

```bash
uv run research clear-cache
```

Disable caching for a single request:

```bash
uv run research research "123 Main St" --no-cache
```

## Configuration

The application uses a `config.json` file in the project root. Key configuration options:

```json
{
    "cache_enabled": true,
    "cache_ttl_hours": 24,
    "timeout_seconds": 30,
    "providers": {
        "flood_zone": {
            "enabled": true,
            "cache_enabled": true
        },
        "walkbike_score": {
            "enabled": true,
            "cache_enabled": true
        },
        "railroads": {
            "raillines_path": "/path/to/railroad/data.geojson",
            "enabled": true,
            "cache_enabled": true
        }
    }
}
```

### Cache Configuration

- `cache_enabled`: Global cache enable/disable
- `cache_ttl_hours`: How long to keep cached data (default: 24 hours)
- `providers.{provider}.cache_enabled`: Per-provider cache control

## Environment Variables

Create a `.env` file with the following variables:

```env
GOOGLE_MAPS_API_KEY=your_api_key_here
NATIONAL_FLOOD_DATA_API_KEY=your_api_key_here
NATIONAL_FLOOD_DATA_CLIENT_ID=your_client_id_here
WALKSCORE_API_KEY=your_api_key_here
```

## Caching System

The caching system automatically stores provider responses to avoid redundant API calls:

- **Cache Key**: Generated from coordinates and provider name
- **Storage**: JSON files in the `cache/` directory
- **TTL**: Configurable expiration time (default: 24 hours)
- **Per-provider**: Each provider can have caching individually enabled/disabled

### Cache Benefits

- **Faster responses**: Cached data is returned immediately
- **Reduced API costs**: Fewer external API calls
- **Offline capability**: Previously researched places work without internet
- **Development efficiency**: Faster iteration during development

### Cache Management Commands

```bash
# View cache statistics
uv run research cache-stats

# Clear all cache
uv run research clear-cache

# Clear cache for specific provider (when implemented)
uv run research clear-cache --provider flood_zone

# Bypass cache for one request
uv run research research "address" --no-cache
```

## Available Providers

1. **Flood Zone Provider**: FEMA flood zone data
2. **Walk/Bike Score Provider**: Walkability and bikeability scores
3. **Railroad Provider**: Distance to nearest railroad lines

## Development

Install development dependencies:

```bash
uv sync --dev
```

Run tests:

```bash
uv run pytest
```
