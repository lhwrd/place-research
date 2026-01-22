# Enrichment Components

This directory contains modular enrichment components for displaying property enrichment data from various backend providers.

## Architecture

The enrichment system uses a **registry pattern** to make it easy to add new enrichment components without modifying the main PropertyDetailPage.

### Key Components

1. **EnrichmentCard** - Wrapper component providing consistent styling for all enrichments
2. **Individual Enrichment Components** - Each provider type has its own component
3. **enrichmentRegistry.tsx** - Maps provider names to components and handles rendering logic
4. **EnrichmentSummary** - Displays enrichment metadata

## File Structure

```
enrichments/
├── EnrichmentCard.tsx          # Base wrapper component
├── enrichmentRegistry.tsx      # Registry for all enrichment components
├── EnrichmentSummary.tsx       # Enrichment metadata display
├── index.ts                    # Barrel exports
├── WalkScoreEnrichment.tsx     # Walk/Bike/Transit scores
├── AirQualityEnrichment.tsx    # Air quality data
├── ClimateEnrichment.tsx       # Climate averages
├── FloodZoneEnrichment.tsx     # Flood zone information
├── TransportationEnrichment.tsx # Highway and railroad data
├── NearbyPlacesEnrichment.tsx  # Nearby places
└── CustomLocationsEnrichment.tsx # Custom location distances
```

## Adding a New Enrichment Component

To add support for a new backend provider:

### Step 1: Create the Component

Create a new file in `components/enrichments/` (e.g., `SchoolsEnrichment.tsx`):

```tsx
import { Grid, Typography } from "@mui/material";
import { GraduationCap } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface SchoolData {
  name: string;
  rating: number;
  distance_miles: number;
}

interface SchoolsEnrichmentProps {
  data: {
    schools: SchoolData[];
  };
  cached?: boolean;
}

export const SchoolsEnrichment = ({ data, cached }: SchoolsEnrichmentProps) => {
  return (
    <EnrichmentCard title="Nearby Schools" icon={GraduationCap} cached={cached}>
      <Grid container spacing={2}>
        {data.schools.map((school, index) => (
          <Grid size={{ xs: 12, sm: 6 }} key={index}>
            <Typography variant="body2" fontWeight="bold">
              {school.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Rating: {school.rating}/10 • {school.distance_miles} mi
            </Typography>
          </Grid>
        ))}
      </Grid>
    </EnrichmentCard>
  );
};
```

### Step 2: Export the Component

Add to `index.ts`:

```tsx
export { SchoolsEnrichment } from "./SchoolsEnrichment";
```

### Step 3: Register the Component

Add to `enrichmentRegistry.tsx` in the `enrichmentRegistry` array:

```tsx
{
  priority: 8, // Choose an appropriate priority
  shouldRender: (providers) =>
    providers.schools_provider?.success &&
    !!providers.schools_provider.data &&
    !!(providers.schools_provider.data as { schools?: unknown[] })
      .schools?.length,
  render: (providers) => (
    <SchoolsEnrichment
      key="schools"
      data={providers.schools_provider.data as never}
      cached={providers.schools_provider.cached}
    />
  ),
},
```

### That's it! 🎉

The new enrichment component will automatically appear on the PropertyDetailPage when the backend provider returns data.

## Registry Configuration

### Priority

Lower numbers render first. Current priorities:

1. Walk Score
2. Air Quality
3. Climate
4. Flood Zone
5. Transportation
6. Nearby Places
7. Custom Locations

### shouldRender Function

Determines if the enrichment should be displayed. Common patterns:

```tsx
// Single provider with data array
shouldRender: (providers) =>
  providers.provider_name?.success &&
  !!providers.provider_name.data &&
  !!(providers.provider_name.data as { items?: unknown[] }).items?.length;

// Single provider with simple data
shouldRender: (providers) =>
  providers.provider_name?.success && !!providers.provider_name.data;

// Multiple providers (either/or)
shouldRender: (providers) =>
  providers.provider_a?.success || providers.provider_b?.success;
```

### render Function

Returns the React component. Always include:

- Unique `key` prop
- Type casting with `as never` for data prop
- `cached` prop from provider

## Benefits of This Architecture

✅ **Easy to Add** - New enrichments require minimal code
✅ **Modular** - Each enrichment is self-contained
✅ **Maintainable** - Changes to one enrichment don't affect others
✅ **Testable** - Components can be tested individually
✅ **Consistent** - EnrichmentCard ensures uniform styling
✅ **Declarative** - Registry clearly shows all available enrichments
✅ **No Page Edits** - PropertyDetailPage doesn't need modification

## Component Guidelines

1. **Use EnrichmentCard** - Always wrap your content in EnrichmentCard
2. **Include Icons** - Choose an appropriate Lucide icon
3. **Handle Missing Data** - Display "N/A" for null/undefined values
4. **Use Grid Layout** - Keep consistent with Material-UI Grid
5. **Type Props** - Create interfaces for your data structure
6. **Keep It Simple** - Each component should display one type of enrichment

## Example: Complex Multi-Provider Enrichment

```tsx
// Transportation handles both highway and railroad data
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
}
```

## Troubleshooting

**Component not rendering?**

- Check the provider name matches exactly (case-sensitive)
- Verify `shouldRender` logic is correct
- Check console logs for enrichment data structure

**Type errors?**

- Use `as never` for data prop type casting
- Define proper TypeScript interfaces for your data

**Styling inconsistent?**

- Use EnrichmentCard wrapper
- Follow Material-UI Grid patterns from existing components
