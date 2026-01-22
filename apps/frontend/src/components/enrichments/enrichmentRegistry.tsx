import { ReactElement } from "react";
import {
  WalkScoreEnrichment,
  AirQualityEnrichment,
  ClimateEnrichment,
  FloodZoneEnrichment,
  TransportationEnrichment,
  NearbyPlacesEnrichment,
  CustomLocationsEnrichment,
} from "./index";

/**
 * Interface for enrichment provider data
 */
interface EnrichmentProviderData {
  success: boolean;
  cached?: boolean;
  data?: unknown;
}

/**
 * Interface for enrichment component renderer
 */
interface EnrichmentRenderer {
  /**
   * Check if this enrichment should be displayed
   * @param providers - All enrichment provider data
   * @returns true if the enrichment should be rendered
   */
  shouldRender: (providers: Record<string, EnrichmentProviderData>) => boolean;

  /**
   * Render the enrichment component
   * @param providers - All enrichment provider data
   * @returns The enrichment component
   */
  render: (providers: Record<string, EnrichmentProviderData>) => ReactElement;

  /**
   * Priority for rendering (lower numbers render first)
   */
  priority?: number;
}

/**
 * Registry of all enrichment renderers
 *
 * To add a new enrichment component:
 * 1. Create a new component in the enrichments folder
 * 2. Add it to the registry with shouldRender and render functions
 * 3. Set an appropriate priority (optional)
 */
export const enrichmentRegistry: EnrichmentRenderer[] = [
  // WalkScore - Priority 1
  {
    priority: 1,
    shouldRender: (providers) => {
      const provider = providers.walk_score_provider;
      const hasData = provider?.success === true && provider?.data != null;
      console.log("WalkScore shouldRender check:", {
        provider,
        hasData,
        success: provider?.success,
        dataNotNull: provider?.data != null,
      });
      return hasData;
    },
    render: (providers) => (
      <WalkScoreEnrichment
        key="walkscore"
        data={providers.walk_score_provider.data as never}
        cached={providers.walk_score_provider.cached}
      />
    ),
  },

  // Air Quality - Priority 2
  {
    priority: 2,
    shouldRender: (providers) =>
      providers.air_quality_provider?.success &&
      !!providers.air_quality_provider.data,
    render: (providers) => (
      <AirQualityEnrichment
        key="air-quality"
        data={providers.air_quality_provider.data as never}
        cached={providers.air_quality_provider.cached}
      />
    ),
  },

  // Climate - Priority 3
  {
    priority: 3,
    shouldRender: (providers) =>
      providers.annual_average_climate_provider?.success &&
      !!providers.annual_average_climate_provider.data,
    render: (providers) => (
      <ClimateEnrichment
        key="climate"
        data={providers.annual_average_climate_provider.data as never}
        cached={providers.annual_average_climate_provider.cached}
      />
    ),
  },

  // Flood Zone - Priority 4
  {
    priority: 4,
    shouldRender: (providers) =>
      providers.flood_zone_provider?.success &&
      !!providers.flood_zone_provider.data,
    render: (providers) => (
      <FloodZoneEnrichment
        key="flood-zone"
        data={providers.flood_zone_provider.data as never}
        cached={providers.flood_zone_provider.cached}
      />
    ),
  },

  // Transportation (Highway & Railroad) - Priority 5
  {
    priority: 5,
    shouldRender: (providers) =>
      providers.highway_provider?.success ||
      providers.railroad_provider?.success,
    render: (providers) => (
      <TransportationEnrichment
        key="transportation"
        highwayData={
          providers.highway_provider?.success
            ? (providers.highway_provider.data as never)
            : undefined
        }
        railroadData={
          providers.railroad_provider?.success
            ? (providers.railroad_provider.data as never)
            : undefined
        }
        highwayCached={providers.highway_provider?.cached}
        railroadCached={providers.railroad_provider?.cached}
      />
    ),
  },

  // Nearby Places - Priority 6
  {
    priority: 6,
    shouldRender: (providers) =>
      providers.places_nearby_provider?.success &&
      !!providers.places_nearby_provider.data &&
      !!(providers.places_nearby_provider.data as { places_nearby?: unknown[] })
        .places_nearby?.length,
    render: (providers) => (
      <NearbyPlacesEnrichment
        key="nearby-places"
        data={providers.places_nearby_provider.data as never}
        cached={providers.places_nearby_provider.cached}
      />
    ),
  },

  // Custom Locations - Priority 7
  {
    priority: 7,
    shouldRender: (providers) =>
      providers.distance_provider?.success &&
      !!providers.distance_provider.data &&
      !!(providers.distance_provider.data as { distances?: unknown[] })
        .distances?.length,
    render: (providers) => (
      <CustomLocationsEnrichment
        key="custom-locations"
        data={providers.distance_provider.data as never}
        cached={providers.distance_provider.cached}
      />
    ),
  },
];

/**
 * Get all enrichment components that should be rendered
 * @param providers - All enrichment provider data
 * @returns Array of enrichment components sorted by priority
 */
export const getEnrichmentComponents = (
  providers: Record<string, EnrichmentProviderData>
): ReactElement[] => {
  console.log("getEnrichmentComponents called with providers:", providers);
  console.log("Provider keys:", Object.keys(providers));

  const components = enrichmentRegistry
    .filter((renderer) => {
      const shouldRender = renderer.shouldRender(providers);
      console.log(
        `Renderer priority ${renderer.priority} shouldRender:`,
        shouldRender
      );
      return shouldRender;
    })
    .sort((a, b) => (a.priority || 999) - (b.priority || 999))
    .map((renderer) => renderer.render(providers));

  console.log(`Rendering ${components.length} enrichment components`);
  return components;
};
