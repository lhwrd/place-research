# engine.py
from .interfaces import PlaceProvider, CityProvider, CountyProvider, StateProvider
from .models import Place
from .config import Config
from .cache import CacheManager


class ResearchEngine:
    def __init__(self, providers, config: Config | None = None):
        self.config = config or Config()
        # Filter providers based on configuration
        self.providers = [
            provider for provider in providers if self._is_provider_enabled(provider)
        ]
        self.cache_manager = CacheManager(config=self.config)

    def _is_provider_enabled(self, provider) -> bool:
        """Check if a provider is enabled based on configuration."""
        provider_name = provider.__class__.__name__.lower().replace("provider", "")
        return self.config.is_provider_enabled(provider_name)

    def _get_provider_name(self, provider) -> str:
        """Get the provider name for caching purposes."""
        return provider.__class__.__name__.lower().replace("provider", "")

    def enrich_place(self, place: Place):
        for provider in self.providers:
            if isinstance(provider, PlaceProvider):
                provider_name = self._get_provider_name(provider)

                # Try to get cached data first
                cached_data = self.cache_manager.get_cached_data(place, provider_name)
                if cached_data:
                    # Apply cached data to place attributes
                    place.attributes.update(cached_data)
                else:
                    # Store attributes before provider call to detect what was added
                    before_attributes = place.attributes.copy()

                    # Fetch fresh data
                    provider.fetch_place_data(place)

                    # Determine what new attributes were added
                    new_attributes = {
                        k: v
                        for k, v in place.attributes.items()
                        if k not in before_attributes or before_attributes[k] != v
                    }

                    # Cache the new attributes
                    if new_attributes:
                        self.cache_manager.cache_data(
                            place, provider_name, new_attributes
                        )

        if place.city:
            for provider in self.providers:
                if isinstance(provider, CityProvider):
                    provider.fetch_city_data(place.city)

        if place.county:
            for provider in self.providers:
                if isinstance(provider, CountyProvider):
                    provider.fetch_county_data(place.county)

        if place.state:
            for provider in self.providers:
                if isinstance(provider, StateProvider):
                    provider.fetch_state_data(place.state)

        return place
