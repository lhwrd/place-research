import { Grid, Typography } from "@mui/material";
import { Cloud } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface ClimateData {
  annual_average_temperature?: number;
  annual_average_precipitation?: number;
}

interface ClimateEnrichmentProps {
  data: ClimateData;
  cached?: boolean;
}

export const ClimateEnrichment = ({ data, cached }: ClimateEnrichmentProps) => {
  return (
    <EnrichmentCard
      title="Annual Climate Averages"
      icon={Cloud}
      cached={cached}
    >
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Average Temperature
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.annual_average_temperature?.toFixed(1)}°F
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Average Precipitation
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.annual_average_precipitation?.toFixed(2)}"
          </Typography>
        </Grid>
      </Grid>
    </EnrichmentCard>
  );
};
