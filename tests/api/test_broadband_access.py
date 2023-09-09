import pytest
from residence_research.api.broadband_access import get_mobile_coverage

def test_get_mobile_coverage():
    # Test case 1: Valid latitude and longitude
    latitude = 37.7749
    longitude = -122.4194

    coverage = get_mobile_coverage(latitude, longitude)
    assert isinstance(coverage, dict)  # Check if the result is a dictionary
    assert 'verizon' in coverage  # Check if Verizon coverage is present
    assert 'att' in coverage  # Check if AT&T coverage is present
    assert 'tmo' in coverage  # Check if T-Mobile coverage is present

    # Test case 2: Invalid latitude and longitude (API request failure)
    latitude = 1000.0
    longitude = -2000.0

    coverage = get_mobile_coverage(latitude, longitude)
    assert isinstance(coverage, dict)  # Check if the result is a dictionary
    assert coverage['verizon'] == 'API request failed'  # Check if Verizon coverage failed
    assert coverage['att'] == 'API request failed'  # Check if AT&T coverage failed
    assert coverage['tmo'] == 'API request failed'  # Check if T-Mobile coverage failed

    # Test case 3: No coverage data available
    latitude = 42.3601
    longitude = -71.0589

    coverage = get_mobile_coverage(latitude, longitude)
    assert isinstance(coverage, dict)  # Check if the result is a dictionary
    assert coverage['verizon'] == 'No coverage data available'  # Check if Verizon has no coverage data
    assert coverage['att'] == 'No coverage data available'  # Check if AT&T has no coverage data
    assert coverage['tmo'] == 'No coverage data available'  # Check if T-Mobile has no coverage data
