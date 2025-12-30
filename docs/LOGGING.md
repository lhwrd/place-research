# Logging & Observability

This guide covers the logging and observability features in place-research, including structured logging, request tracking, performance metrics, and monitoring.

## Overview

Place-research includes a comprehensive logging and observability system designed for production environments:

- **Structured Logging**: JSON-formatted logs for easy parsing and analysis
- **Request Tracking**: Unique request IDs for distributed tracing
- **Performance Metrics**: Request latency, error rates, and endpoint statistics
- **Provider Metrics**: Execution time and success rates for data providers
- **Cache Observability**: Hit rates, miss rates, and cache performance

## Quick Start

### Basic Configuration

The logging system is automatically configured when the API starts. Configure it via environment variables:

```bash
# .env
LOG_LEVEL=INFO
LOG_FORMAT=json  # or 'text' for development, 'color' for colored output
LOG_REQUESTS=true
LOG_RESPONSES=true
LOG_PROVIDER_METRICS=true
LOG_CACHE_OPERATIONS=false  # Set to true for cache debugging
```

### Development vs Production

**Development** (human-readable):

```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=color
```

**Production** (JSON for log aggregation):

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Log Formats

### JSON Format (Production)

Structured JSON logs with consistent fields:

```json
{
  "timestamp": "2024-12-30T19:30:45.123456Z",
  "level": "INFO",
  "logger": "place_research.service",
  "message": "Provider walkbikescore completed in 127.45ms",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "provider": "walkbikescore",
  "event": "provider_completed",
  "duration_ms": 127.45,
  "cache_hit": false
}
```

### Text Format (Development)

Human-readable format for development:

```
2024-12-30 11:30:45 [INFO] place_research.service - Provider walkbikescore completed in 127.45ms [a1b2c3d4]
```

### Color Format (Development)

Same as text format but with colored output for better readability in terminals.

## Request Tracking

Every HTTP request is assigned a unique request ID for distributed tracing.

### Request ID Propagation

```python
# Request ID is automatically:
# 1. Generated for each request
# 2. Added to all log messages
# 3. Included in response headers

# Example response headers:
# X-Request-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Using Request IDs

In your logs, search for a specific request:

```bash
# JSON logs
cat app.log | jq 'select(.request_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890")'

# Text logs
grep "a1b2c3d4" app.log
```

### Programmatic Access

```python
from place_research.logging_config import get_request_id, set_request_id

# Get current request ID
request_id = get_request_id()

# Set request ID (usually done by middleware)
set_request_id("custom-request-id")
```

## Log Context

Add custom context to all log messages within a scope:

```python
from place_research.logging_config import set_log_context, clear_log_context

# Add context
set_log_context(user_id="user123", action="enrich_place")

# All subsequent logs will include this context
logger.info("Processing request")
# => Includes user_id and action in the log

# Clear context when done
clear_log_context()
```

## Performance Metrics

### Accessing Metrics

Metrics are exposed via the `/metrics` endpoint:

```bash
curl http://localhost:8000/metrics
```

Response:

```json
{
  "total_requests": 1523,
  "total_errors": 12,
  "error_rate": 0.0079,
  "avg_duration_ms": 245.67,
  "status_codes": {
    "200": 1487,
    "404": 24,
    "500": 12
  },
  "endpoints": {
    "POST /enrich": {
      "count": 1250,
      "avg_duration_ms": 312.45,
      "min_duration_ms": 89.23,
      "max_duration_ms": 1543.21,
      "errors": 8,
      "error_rate": 0.0064
    },
    "GET /health": {
      "count": 273,
      "avg_duration_ms": 2.34,
      "min_duration_ms": 1.23,
      "max_duration_ms": 8.45,
      "errors": 0,
      "error_rate": 0.0
    }
  }
}
```

### Metrics Collected

- **Request counts**: Total requests processed
- **Error counts**: Total errors encountered
- **Error rate**: Percentage of failed requests
- **Response times**: Average, minimum, maximum per endpoint
- **Status codes**: Distribution of HTTP status codes
- **Per-endpoint stats**: Detailed metrics for each endpoint

## Provider Metrics

When `LOG_PROVIDER_METRICS=true`, provider execution is logged:

```json
{
  "timestamp": "2024-12-30T19:30:45.123456Z",
  "level": "INFO",
  "message": "Provider walkbikescore completed in 127.45ms",
  "provider": "walkbikescore",
  "event": "provider_completed",
  "duration_ms": 127.45,
  "cache_hit": false
}
```

Events logged:

- `provider_started`: Provider begins fetching data
- `provider_completed`: Provider successfully returned data
- `provider_failed`: Provider encountered an error

## Cache Metrics

### Cache Statistics

Access cache statistics via `/cache/stats`:

```bash
curl http://localhost:8000/cache/stats
```

Response:

```json
{
  "enabled": true,
  "hits": 1250,
  "misses": 345,
  "sets": 345,
  "hit_rate": 0.784,
  "size": 345
}
```

### Cache Operation Logging

Enable detailed cache logging for debugging:

```bash
LOG_CACHE_OPERATIONS=true
```

Logs cache hits, misses, and sets:

```json
{
  "timestamp": "2024-12-30T19:30:45.123456Z",
  "level": "INFO",
  "message": "Cache hit for walkbikescore",
  "provider": "walkbikescore",
  "event": "cache_hit"
}
```

**Warning**: Cache operation logging can be verbose. Only enable in development or for troubleshooting.

## Log Timing Utilities

### LogTimer Context Manager

Time operations and automatically log duration:

```python
from place_research.logging_config import LogTimer
import logging

logger = logging.getLogger(__name__)

with LogTimer(logger, "database_query", level=logging.INFO, query_id=123):
    # Perform expensive operation
    results = expensive_database_query()

# Automatically logs:
# Starting database_query
# Completed database_query in 234.56ms
```

If an exception occurs:

```python
with LogTimer(logger, "risky_operation"):
    raise ValueError("Something went wrong")

# Logs:
# Starting risky_operation
# Failed risky_operation after 12.34ms: Something went wrong
```

## Log Levels

Configure via `LOG_LEVEL` environment variable:

- **DEBUG**: Detailed diagnostic information (very verbose)
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages for recoverable issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical failures requiring immediate attention

```bash
# Development
LOG_LEVEL=DEBUG

# Production
LOG_LEVEL=INFO

# Production (quiet)
LOG_LEVEL=WARNING
```

## Request/Response Logging

### Enable/Disable

```bash
# Enable both (default)
LOG_REQUESTS=true
LOG_RESPONSES=true

# Disable for performance (not recommended)
LOG_REQUESTS=false
LOG_RESPONSES=false
```

### Request Logs

```json
{
  "timestamp": "2024-12-30T19:30:45.123456Z",
  "level": "INFO",
  "message": "POST /enrich",
  "event": "request_started",
  "method": "POST",
  "path": "/enrich",
  "query_params": "lat=40.7128&lng=-74.0060",
  "client_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

### Response Logs

```json
{
  "timestamp": "2024-12-30T19:30:45.567890Z",
  "level": "INFO",
  "message": "POST /enrich - 200 - 245.67ms",
  "event": "request_completed",
  "method": "POST",
  "path": "/enrich",
  "status_code": 200,
  "duration_ms": 245.67
}
```

## Integration with Log Aggregation

### Elasticsearch/Logstash/Kibana (ELK)

JSON logs are compatible with ELK stack:

```bash
# Output to file for Logstash
LOG_FORMAT=json
```

Logstash configuration:

```ruby
input {
  file {
    path => "/var/log/place-research/app.log"
    codec => "json"
  }
}

filter {
  # Logs are already JSON, no parsing needed
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "place-research-%{+YYYY.MM.dd}"
  }
}
```

### Datadog

```bash
# Configure Datadog agent to tail logs
# /etc/datadog-agent/conf.d/place_research.yaml
logs:
  - type: file
    path: /var/log/place-research/app.log
    service: place-research
    source: python
```

### CloudWatch

```bash
# Use AWS CloudWatch agent to ship logs
# JSON format is automatically parsed
LOG_FORMAT=json
```

## Monitoring Best Practices

### Production Recommendations

1. **Use JSON format**: Easier for log aggregation tools

   ```bash
   LOG_FORMAT=json
   ```

2. **Set appropriate log level**: INFO for production, DEBUG only when troubleshooting

   ```bash
   LOG_LEVEL=INFO
   ```

3. **Disable cache operation logging**: Too verbose for production

   ```bash
   LOG_CACHE_OPERATIONS=false
   ```

4. **Enable metrics collection**: Monitor performance and errors

   - Access `/metrics` endpoint
   - Set up alerts on error_rate and avg_duration_ms

5. **Monitor specific metrics**:
   - Error rate > 1%: Investigate errors
   - Average duration > 1000ms: Performance issue
   - Cache hit rate < 50%: Consider TTL adjustments

### Development Recommendations

1. **Use colored output**: Easier to read in terminal

   ```bash
   LOG_FORMAT=color
   LOG_LEVEL=DEBUG
   ```

2. **Enable cache logging**: Understand cache behavior

   ```bash
   LOG_CACHE_OPERATIONS=true
   ```

3. **Monitor individual providers**: Check provider execution times
   ```bash
   LOG_PROVIDER_METRICS=true
   ```

## Alerting

Set up alerts based on metrics:

### Error Rate Alert

```python
# Pseudo-code for monitoring system
if metrics["error_rate"] > 0.01:  # > 1%
    send_alert("High error rate detected")
```

### Latency Alert

```python
if metrics["avg_duration_ms"] > 1000:  # > 1 second
    send_alert("High latency detected")
```

### Provider-Specific Alert

```python
endpoint_metrics = metrics["endpoints"]["POST /enrich"]
if endpoint_metrics["avg_duration_ms"] > 500:
    send_alert("Enrichment endpoint slow")
```

## Troubleshooting

### No logs appearing

1. Check log level: Set to DEBUG temporarily

   ```bash
   LOG_LEVEL=DEBUG
   ```

2. Verify logging is configured: Check API startup logs
   ```
   INFO src.place_research.logging_config: Logging configured: level=INFO, format=json
   ```

### Logs are too verbose

1. Increase log level: INFO or WARNING

   ```bash
   LOG_LEVEL=WARNING
   ```

2. Disable cache operation logging:
   ```bash
   LOG_CACHE_OPERATIONS=false
   ```

### Request ID not in logs

- Check that middleware is properly configured
- Request ID only appears for HTTP requests, not CLI usage

### Metrics not available

- Ensure middleware is initialized: Check `/metrics` endpoint
- Metrics reset on application restart

## Example: Complete Logging Configuration

```bash
# .env - Production
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_REQUESTS=true
LOG_RESPONSES=true
LOG_PROVIDER_METRICS=true
LOG_CACHE_OPERATIONS=false
```

```bash
# .env - Development
LOG_LEVEL=DEBUG
LOG_FORMAT=color
LOG_REQUESTS=true
LOG_RESPONSES=true
LOG_PROVIDER_METRICS=true
LOG_CACHE_OPERATIONS=true
```

## Programmatic Logging

### In Your Code

```python
import logging
from place_research.logging_config import LogTimer, set_log_context

logger = logging.getLogger(__name__)

def process_place(place_id: str):
    # Add context
    set_log_context(place_id=place_id)

    # Log with context
    logger.info("Processing place")

    # Time an operation
    with LogTimer(logger, "fetch_data", place_id=place_id):
        data = fetch_external_data(place_id)

    # Log success
    logger.info("Place processed successfully")
```

## Performance Impact

The logging system is designed for minimal performance impact:

- **Request logging**: ~0.1ms overhead per request
- **JSON formatting**: ~0.05ms per log message
- **Metrics collection**: ~0.02ms per request
- **Context management**: Negligible (using contextvars)

Total overhead: **<0.5ms per request** in production with INFO level.

## Next Steps

- [Error Handling](ERROR_HANDLING.md) - Exception handling and validation
- [Authentication](AUTHENTICATION.md) - API security and authorization
- [Caching](CACHING.md) - Performance optimization
