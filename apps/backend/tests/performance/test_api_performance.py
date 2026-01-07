"""Performance tests for API endpoints."""

import time
from statistics import mean, stdev

import pytest
from fastapi.testclient import TestClient


class TestAPIPerformance:
    """Performance benchmarks for API endpoints."""

    @pytest.mark.performance
    def test_property_search_performance(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_google_maps_api,
        mock_property_data_api,
    ):
        """Test property search endpoint performance."""
        times = []
        iterations = 50

        for _ in range(iterations):
            start = time.time()
            response = client.post(
                "/api/v1/properties/search",
                headers=auth_headers,
                json={"address": f"123 Test St, Seattle, WA"},
            )
            end = time.time()

            assert response.status_code == 200
            times.append(end - start)

        avg_time = mean(times)
        std_dev = stdev(times) if len(times) > 1 else 0

        print(f"\nProperty Search Performance:")
        print(f"  Average:  {avg_time*1000:.2f}ms")
        print(f"  Std Dev: {std_dev*1000:.2f}ms")
        print(f"  Min: {min(times)*1000:.2f}ms")
        print(f"  Max: {max(times)*1000:.2f}ms")

        # Assert performance threshold (adjust as needed)
        assert avg_time < 0.5, f"Average response time {avg_time}s exceeds 500ms threshold"

    @pytest.mark.performance
    def test_concurrent_requests(self, client: TestClient, auth_headers: dict):
        """Test handling concurrent requests."""
        import concurrent.futures

        def make_request():
            return client.get("/api/v1/auth/me", headers=auth_headers)

        # Execute 5 concurrent requests (reduced from 20 to avoid SQLite connection pool issues)
        # Note: SQLite with TestClient has limitations for high concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(r.status_code == 200 for r in results)
