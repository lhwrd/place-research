"""Conftest for integration tests that need real API implementations."""

import importlib.util
from pathlib import Path

import pytest

# Load the real GoogleMapsAPI before conftest mocks it
# This needs to happen at module level, before pytest_configure runs
_real_gmaps_module = None


def _load_real_google_maps_api():
    """Load the real GoogleMapsAPI implementation."""
    global _real_gmaps_module
    if _real_gmaps_module is not None:
        return _real_gmaps_module

    # Load the module from source directly
    module_path = (
        Path(__file__).parent.parent.parent.parent / "app" / "integrations" / "google_maps_api.py"
    )
    spec = importlib.util.spec_from_file_location("real_google_maps_api", module_path)
    _real_gmaps_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_real_gmaps_module)
    return _real_gmaps_module


# Load it immediately at import time
_real_module = _load_real_google_maps_api()


@pytest.fixture(autouse=True)
def unmock_google_maps_api():
    """Restore real GoogleMapsAPI implementation for unit tests."""
    # Replace the mock in the app.integrations.google_maps_api module
    import app.integrations.google_maps_api as gmaps_module

    original_class = gmaps_module.GoogleMapsAPI
    gmaps_module.GoogleMapsAPI = _real_module.GoogleMapsAPI

    yield

    # Restore the mock for other tests
    gmaps_module.GoogleMapsAPI = original_class
