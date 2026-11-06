"""Provider registry for dynamic loading and management of enrichment providers."""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
)

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for discovering and managing enrichment providers.

    Automatically discovers all provider classes in the providers directory
    and makes them available for use.
    """

    _instance = None
    _providers: Dict[str, Type[BaseEnrichmentProvider]] = {}
    _initialized = False

    def __new__(cls):
        """Singleton pattern to ensure only one registry exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the registry and discover providers."""
        if not self._initialized:
            self.discover_providers()
            self._initialized = True

    def discover_providers(self) -> None:
        """
        Automatically discover and register all provider classes.

        Scans the providers directory and registers any class that
        inherits from BaseEnrichmentProvider.
        """
        providers_dir = Path(__file__).parent / "providers"

        if not providers_dir.exists():
            logger.warning(f"Providers directory not found: {providers_dir}")
            return

        # Import all modules in the providers directory
        for module_info in pkgutil.iter_modules([str(providers_dir)]):
            try:
                module = importlib.import_module(
                    f"app.services.enrichment.providers.{module_info.name}"
                )

                # Find all provider classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseEnrichmentProvider)
                        and obj is not BaseEnrichmentProvider
                    ):
                        self.register_provider(obj)

            except Exception as e:
                logger.error(f"Failed to load provider module {module_info.name}: {str(e)}")

        logger.info(f"Discovered {len(self.__class__._providers)} enrichment providers")

    def register_provider(self, provider_class: Type[BaseEnrichmentProvider]) -> None:
        """
        Register a provider class.

        Args:
            provider_class: Provider class to register
        """
        # Instantiate to get metadata
        try:
            instance = provider_class()
            provider_name = instance.metadata.name

            if provider_name in self.__class__._providers:
                logger.warning(f"Provider {provider_name} already registered, overwriting")

            self.__class__._providers[provider_name] = provider_class
            logger.info(f"Registered provider: {provider_name}")

        except Exception as e:
            logger.error(f"Failed to register provider {provider_class.__name__}: {str(e)}")

    def get_provider(self, name: str) -> Optional[BaseEnrichmentProvider]:
        """
        Get a provider instance by name.

        Args:
            name: Provider name

        Returns:
            Provider instance or None if not found
        """
        provider_class = self.__class__._providers.get(name)
        if provider_class:
            return provider_class()
        return None

    def get_all_providers(self) -> List[BaseEnrichmentProvider]:
        """
        Get instances of all registered providers.

        Returns:
            List of provider instances
        """
        return [cls() for cls in self.__class__._providers.values()]

    def get_providers_by_category(self, category: ProviderCategory) -> List[BaseEnrichmentProvider]:
        """
        Get all providers in a specific category.

        Args:
            category:  Provider category

        Returns:
            List of provider instances in the category
        """
        providers = []
        for provider_class in self.__class__._providers.values():
            instance = provider_class()
            if instance.metadata.category == category:
                providers.append(instance)
        return providers

    def get_enabled_providers(self) -> List[BaseEnrichmentProvider]:
        """
        Get all enabled providers.

        Returns:
            List of enabled provider instances
        """
        providers = []
        for provider_class in self.__class__._providers.values():
            instance = provider_class()
            if instance.metadata.enabled:
                providers.append(instance)
        return providers

    def list_providers(self) -> List[ProviderMetadata]:
        """
        List metadata for all registered providers.

        Returns:
            List of provider metadata
        """
        metadata_list = []
        for provider_class in self.__class__._providers.values():
            instance = provider_class()
            metadata_list.append(instance.metadata)
        return metadata_list


# Global registry instance
registry = ProviderRegistry()
