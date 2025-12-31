# Quick Start Guide - Place Research API

## 🚀 Start the API in 30 Seconds

```bash
# 1. Ensure dependencies are installed
uv sync

# 2. Set your API keys (optional - works without them too)
export WALKSCORE_API_KEY="your-key"
export GOOGLE_MAPS_API_KEY="your-key"

# 3. Start the server
research serve --reload
```

That's it! API is now running at `http://localhost:8000`

## 📡 Quick API Calls

### Health Check

```bash
curl http://localhost:8000/health
```

### See Which Providers Are Enabled

```bash
curl http://localhost:8000/providers
```

### Enrich a Place

```bash
# Simple GET request
curl "http://localhost:8000/enrich?geolocation=40.7128;-74.0060"

# POST with JSON (more options)
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1600 Amphitheatre Parkway, Mountain View, CA",
    "geolocation": "37.4220;-122.0841"
  }'
```

## 🌐 Interactive Documentation

Open in your browser:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 💻 Use in Your Code

### Python

```python
from place_research.service import PlaceEnrichmentService
from place_research.config import get_settings
from place_research.models import Place

# Initialize
settings = get_settings()
service = PlaceEnrichmentService(settings)

# Enrich a place
place = Place(address="123 Main St", geolocation="40.7128;-74.0060")
result = service.enrich_place(place)

# Access results
if result.walk_bike_score:
    print(f"Walk Score: {result.walk_bike_score.walk_score}")

if result.highway:
    print(f"Nearest Highway: {result.highway.nearest_highway}")

# Check for errors
for error in result.errors:
    print(f"Error in {error.provider_name}: {error.error_message}")
```

### JavaScript/TypeScript

```javascript
// Fetch API
const response = await fetch("http://localhost:8000/enrich", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    address: "123 Main St",
    geolocation: "40.7128;-74.0060",
  }),
});

const data = await response.json();
console.log("Walk Score:", data.walk_bike_score?.walk_score);
console.log("Air Quality:", data.air_quality?.category);
```

### curl (Bash)

```bash
#!/bin/bash

# Save response to file
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"geolocation": "40.7128;-74.0060"}' \
  -o enrichment_result.json

# Pretty print with jq
curl -s http://localhost:8000/enrich?geolocation=40.7128;-74.0060 | jq '.'
```

## 🔧 Configuration

### Option 1: Environment Variables

```bash
export WALKSCORE_API_KEY="your-key"
export AIRNOW_API_KEY="your-key"
export GOOGLE_MAPS_API_KEY="your-key"
```

### Option 2: .env File

```bash
# Copy template
cp .env.example .env

# Edit .env
vim .env
```

### Option 3: Programmatic

```python
from place_research.config import Settings

settings = Settings(
    walkscore_api_key="your-key",
    google_maps_api_key="your-key"
)
```

## 📊 Response Format

```json
{
  "place_id": "123",
  "walk_bike_score": {
    "walk_score": 85,
    "walk_description": "Very Walkable",
    "bike_score": 75,
    "bike_description": "Very Bikeable"
  },
  "air_quality": {
    "aqi": "45",
    "category": "Good"
  },
  "highway": {
    "nearest": "I-280",
    "distance_miles": 0.8
  },
  "railroad": {
    "nearest": "Caltrain",
    "distance_miles": 1.2
  },
  "walmart": {
    "nearest": "Walmart Supercenter",
    "distance_miles": 3.5
  },
  "flood_zone": "X",
  "climate": {
    "avg_temperature": 60.5,
    "avg_precipitation": 21.3,
    "avg_snowfall": 0.0
  },
  "distances": {
    "closest_member": "Mom",
    "distance_miles": 45.2
  },
  "errors": []
}
```

## 🎯 Common Use Cases

### 1. Real Estate App

Enrich property listings with walkability, air quality, proximity data.

### 2. Moving Planner

Compare multiple locations for someone relocating.

### 3. Route Planner

Find places along a route and check their amenities.

### 4. Data Analysis

Batch process many locations for research or analytics.

### 5. Mobile App Backend

Provide enriched location data to mobile applications.

## 🐛 Troubleshooting

### API Won't Start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Use a different port
research serve --port 8080
```

### Providers Disabled

```bash
# Check which providers are enabled
curl http://localhost:8000/providers

# They need API keys - check .env file
cat .env
```

### Import Errors

```bash
# Reinstall dependencies
uv sync

# Verify installation
python -c "from place_research.api import app; print('OK')"
```

## 📚 Learn More

- [Full API Documentation](API_README.md)
- [Implementation Details](IMPLEMENTATION_SUMMARY.md)
- [Code Examples](examples/api_usage.py)
- [Test Suite](tests/test_api_architecture.py)

## 🤝 Contributing

The new architecture makes it easy to add providers:

```python
from place_research.interfaces import PlaceProvider
from place_research.models.results import YourResult

class YourProvider(ProviderNameMixin):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_place_data(self, place: Place) -> YourResult:
        # Fetch data from your API
        data = requests.get(f"https://api.example.com?lat={lat}&lng={lng}")

        # Return typed result
        return YourResult(your_field=data['value'])
```

Register in [service.py](src/place_research/service.py) and you're done!

---

**Questions?** Check the [full documentation](API_README.md) or examine the [examples](examples/api_usage.py).
