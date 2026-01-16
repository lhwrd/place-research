# Place Research - API-First Architecture

A data enrichment system that gathers information about physical locations from multiple external APIs and data sources.

## 🎯 What's New - API-First Design

The package has been refactored with a clean, layered architecture that separates concerns and enables multiple frontends:

```
┌─────────────────────────────────────────────┐
│         Frontends (Multiple)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ REST API │  │   CLI    │  │  Web UI  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
├───────┴──────────────┴──────────────┴───────┤
│          Service Layer                      │
│      (PlaceEnrichmentService)               │
├─────────────────────────────────────────────┤
│          Provider Layer                     │
│  WalkScore │ AirQuality │ FloodZone │ ...   │
├─────────────────────────────────────────────┤
│      Repository Layer (Storage)             │
│      NocoDB │ InMemory │ PostgreSQL         │
└─────────────────────────────────────────────┘
```

### Key Improvements

✅ **API-First**: FastAPI REST API for enriching places from any frontend
✅ **Service Layer**: Clean business logic separate from infrastructure
✅ **Repository Pattern**: Swap storage backends (NocoDB, in-memory, etc.)
✅ **Configuration Management**: Type-safe settings with Pydantic
✅ **Result Objects**: Providers return typed results, not mutate objects
✅ **Better Testing**: Dependency injection enables mocking and testing

## 🚀 Quick Start

### 1. Start the API Server

```bash
# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Start the server
research serve

# Or with custom settings
research serve --host 0.0.0.0 --port 8000 --reload
```

### 2. Use the API

The API will be available at `http://localhost:8000`

#### Health Check

```bash
curl http://localhost:8000/health
```

#### Check Provider Status

```bash
curl http://localhost:8000/providers
```

Returns which providers are enabled and their configuration status:

```json
{
  "enabled_providers": ["walkbikescore", "highway", "railroad"],
  "provider_details": {
    "walkbikescore": {
      "enabled": true,
      "required_config": ["WALKSCORE_API_KEY"],
      "missing_config": []
    },
    "airquality": {
      "enabled": false,
      "required_config": ["AIRNOW_API_KEY"],
      "missing_config": ["AIRNOW_API_KEY"]
    }
  }
}
```

#### Enrich a Place

**POST Request:**

```bash
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1600 Amphitheatre Parkway, Mountain View, CA",
    "geolocation": "37.4220;-122.0841"
  }'
```

**GET Request (convenience):**

```bash
curl "http://localhost:8000/enrich?address=1600%20Amphitheatre%20Parkway&geolocation=37.4220;-122.0841"
```

**Response:**

```json
{
  "place_id": null,
  "walk_bike_score": {
    "walk_score": 85,
    "walk_description": "Very Walkable",
    "bike_score": 75,
    "bike_description": "Very Bikeable"
  },
  "highway": {
    "nearest": "US-101",
    "distance_miles": 0.5
  },
  "errors": []
}
```

### 3. Interactive API Documentation

FastAPI provides automatic interactive docs:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 📚 Architecture Details

### Service Layer

The `PlaceEnrichmentService` is the core business logic:

```python
from place_research.config import get_settings
from place_research.service import PlaceEnrichmentService
from place_research.models import Place

# Initialize service
settings = get_settings()
service = PlaceEnrichmentService(settings)

# Enrich a place
place = Place(address="123 Main St", geolocation="40.7128;-74.0060")
result = service.enrich_place(place)

# Check results
print(f"Walk Score: {result.walk_bike_score.walk_score}")
print(f"Nearest Highway: {result.highway.nearest_highway}")
print(f"Errors: {len(result.errors)}")
```

### Configuration

All settings are managed through Pydantic Settings in [config.py](src/place_research/config.py):

```python
from place_research.config import Settings, get_settings

# Load from environment
settings = get_settings()

# Or create manually
settings = Settings(
    walkscore_api_key="your-key",
    google_maps_api_key="your-key"
)

# Validate provider config
missing = settings.validate_provider_config("WalkBikeScoreProvider")
```

### Repository Pattern

Swap storage backends easily:

```python
from place_research.repositories import InMemoryRepository, NocoDBRepository
from place_research.nocodb import NocoDBClient

# For testing
repo = InMemoryRepository()

# For production
client = NocoDBClient(url="...", token="...")
repo = NocoDBRepository(client)

# Use with service
service = PlaceEnrichmentService(settings, repository=repo)
```

### Result Objects

Providers return typed results instead of mutating Place objects:

```python
from place_research.models.results import WalkBikeScoreResult, HighwayResult

# Clear contracts
walk_result = WalkBikeScoreResult(
    walk_score=85,
    walk_description="Very Walkable",
    bike_score=75,
    bike_description="Very Bikeable"
)

# Structured error handling
from place_research.models.results import ProviderError

error = ProviderError(
    provider_name="airquality",
    error_message="API timeout",
    error_type="API_ERROR"
)
```

## 🔧 Configuration

Create a `.env` file with your API keys and paths:

```bash
# API Keys
WALKSCORE_API_KEY=your_key_here
AIRNOW_API_KEY=your_key_here
GOOGLE_MAPS_API_KEY=your_key_here
NATIONAL_FLOOD_DATA_API_KEY=your_key_here

# Data Files
RAILLINES_PATH=/path/to/railroads.geojson
ANNUAL_CLIMATE_PATH=/path/to/climate.csv

# NocoDB (for CLI)
NOCODB_URL=https://your-nocodb-instance.com
NOCODB_TOKEN=your_token
NOCODB_TABLE_ID=your_table_id

# API Server
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

## 📖 Available Providers

| Provider             | Data Source         | Required Config                             |
| -------------------- | ------------------- | ------------------------------------------- |
| WalkBikeScore        | Walk Score API      | `WALKSCORE_API_KEY`                         |
| AirQuality           | AirNow API          | `AIRNOW_API_KEY`                            |
| FloodZone            | National Flood Data | `NATIONAL_FLOOD_DATA_API_KEY`               |
| Highway              | OpenStreetMap       | None                                        |
| Railroad             | Local GeoJSON       | `RAILLINES_PATH`                            |
| Walmart              | Google Maps         | `GOOGLE_MAPS_API_KEY`                       |
| Distance    | Google Maps         | `GOOGLE_MAPS_API_KEY`                       |
| AnnualAverageClimate | Local CSV           | `ANNUAL_CLIMATE_PATH`                       |

## 🔄 Migration Guide

### From Old CLI to New API

**Old approach:**

```python
# Direct provider instantiation, tight coupling
providers = [WalkBikeScoreProvider(), HighwayProvider()]
engine = ResearchEngine(providers)
engine.enrich_place(place)  # Mutates place object
```

**New approach:**

```python
# Service layer with dependency injection
settings = get_settings()
service = PlaceEnrichmentService(settings)
result = service.enrich_place(place)  # Returns typed result
```

### Backwards Compatibility

The old CLI `research update` command still works and will continue to work during the migration period. New code should use the service layer.

## 🧪 Testing

The new architecture makes testing much easier:

```python
from place_research.config import Settings
from place_research.service import PlaceEnrichmentService
from place_research.repositories import InMemoryRepository

# Create test settings
settings = Settings(walkscore_api_key="test-key")

# Use in-memory repository
repo = InMemoryRepository()

# Inject dependencies
service = PlaceEnrichmentService(settings, repository=repo)

# Test enrichment
place = Place(address="Test", geolocation="0;0")
result = service.enrich_place(place)

assert result.walk_bike_score is not None
assert len(result.errors) == 0
```

## 📝 CLI Commands

```bash
# Start API server
research serve [--host HOST] [--port PORT] [--reload]

# Update NocoDB table (legacy command)
research update --api-key KEY --base-url URL --table-id ID

# Debug mode
research --debug serve
```

## 🔮 Future Enhancements

- [ ] Async provider execution for parallel enrichment
- [ ] Provider caching to reduce API calls
- [ ] GraphQL API alongside REST
- [ ] Webhook support for async enrichment
- [ ] Rate limiting and authentication
- [ ] Provider marketplace/registry
- [ ] Batch enrichment endpoints
- [ ] WebSocket support for real-time updates

## 📄 API Endpoints

| Method | Endpoint     | Description                             |
| ------ | ------------ | --------------------------------------- |
| GET    | `/`          | API information                         |
| GET    | `/health`    | Health check                            |
| GET    | `/providers` | List all providers and their status     |
| POST   | `/enrich`    | Enrich a place (JSON body)              |
| GET    | `/enrich`    | Enrich a place (query params)           |
| GET    | `/docs`      | Interactive API documentation (Swagger) |
| GET    | `/redoc`     | Alternative API documentation (ReDoc)   |

## 🤝 Contributing

The new architecture makes contributing easier:

1. **Add a new provider**: Implement `PlaceProvider` protocol and return a Result object
2. **Add a new storage backend**: Implement `PlaceRepository` protocol
3. **Add a new frontend**: Use `PlaceEnrichmentService` as your backend
4. **Add tests**: Use `InMemoryRepository` and mock providers

## 📜 License

[Add your license here]

## 🙏 Credits

Built with:

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Uvicorn](https://www.uvicorn.org/) - ASGI server
- [Click](https://click.palletsprojects.com/) - CLI framework
