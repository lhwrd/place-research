# engine.py

import logging

from .interfaces import PlaceProvider
from .models import Place


class ResearchEngine:
    def __init__(self, providers):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Initializing ResearchEngine with providers: %s", providers)
        # Filter providers based on configuration
        self.providers = providers

    def enrich_place(self, place: Place):
        self.logger.debug("Enriching place: %s", place)
        for provider in self.providers:
            self.logger.debug("Using provider: %s", provider)
            if isinstance(provider, PlaceProvider):
                try:
                    provider.fetch_place_data(place)
                    self.logger.debug("Provider %s enriched place: %s", provider, place)
                except Exception as e:
                    self.logger.error(
                        "Error in provider %s: %s", provider, e, exc_info=True
                    )
        self.logger.info("Finished enriching place: %s", place.id)
        return place
