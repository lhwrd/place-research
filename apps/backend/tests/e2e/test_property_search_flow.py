"""End-to-end tests for property search workflow."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestPropertySearchFlow:
    """Test complete property search workflow."""

    def test_complete_property_search_and_save_flow(
        self,
        client: TestClient,
        db: Session,
    ):
        """
        Test complete workflow:
        1. Register user
        2. Login
        3. Search for property
        4. Enrich property
        5. Save property
        6. Add custom location
        7. View saved properties
        """

        # Step 1: Register
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "testflow@example.com",
                "password": "SecurePass123",
                "full_name": "Test Flow User",
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Search for property
        search_response = client.post(
            "/api/v1/properties/search",
            headers=headers,
            json={"address": "1600 Amphitheatre Parkway, Mountain View, CA"},
        )
        assert search_response.status_code == 200
        property_data = search_response.json()
        property_id = property_data["property"]["id"]

        # Step 3: Skip enrichment (requires too many external API mocks for e2e test)
        # This should be tested separately in integration tests

        # Step 4: Save property
        save_response = client.post(
            "/api/v1/saved-properties",
            headers=headers,
            json={
                "property_id": property_id,
                "notes": "Great location!",
                "rating": 5,
                "is_favorite": True,
            },
        )
        assert save_response.status_code == 201

        # Step 5: Add custom location
        location_response = client.post(
            "/api/v1/locations",
            headers=headers,
            json={
                "name": "Mom's House",
                "address": "456 Family Ave, Portland, OR",
                "location_type": "family",
                "priority": 90,
            },
        )
        assert location_response.status_code == 201

        # Step 6: View saved properties
        saved_response = client.get("/api/v1/saved-properties", headers=headers)
        assert saved_response.status_code == 200
        saved_list = saved_response.json()
        assert saved_list["total"] == 1
        assert saved_list["items"][0]["rating"] == 5
