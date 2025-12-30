"""Quick test to verify providers run in parallel."""

import asyncio
import time

from src.place_research.config import get_settings
from src.place_research.models import Place
from src.place_research.service import PlaceEnrichmentService


async def main():
    """Test that providers run in parallel."""
    settings = get_settings()
    service = PlaceEnrichmentService(settings)

    # Create a test place
    place = Place(
        id="test-1",
        address="1600 Amphitheatre Parkway, Mountain View, CA",
        latitude=37.4224764,
        longitude=-122.0842499,
    )

    print(f"\n🚀 Running enrichment with {len(service.providers)} providers...")
    print(f"Providers: {[p.name for p in service.providers]}\n")

    start = time.perf_counter()
    result = await service.enrich_place(place)
    duration = time.perf_counter() - start

    print(f"✅ Enrichment completed in {duration:.2f} seconds")
    print(f"   Successful providers: {len(service.providers) - len(result.errors)}")
    print(f"   Errors: {len(result.errors)}")

    if result.errors:
        print("\n⚠️  Errors encountered:")
        for error in result.errors:
            print(f"   - {error.provider_name}: {error.error_message}")

    print(
        f"\n💡 Note: With async parallel execution, {len(service.providers)} providers "
    )
    print(f"   should complete in roughly the time of the slowest provider,")
    print(f"   not the sum of all provider times (sequential execution).")


if __name__ == "__main__":
    asyncio.run(main())
