# Multi-stage build for the FastAPI backend.
# Every dependency ships a manylinux wheel (pyogrio bundles GDAL, shapely bundles
# GEOS), so no system packages or compilers are needed.
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.16 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

# Runtime stage
FROM python:3.13-slim

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser app ./app

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
