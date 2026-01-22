import { Grid, Typography } from "@mui/material";
import { Droplets } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface FloodZoneData {
  flood_zone?: string;
  flood_risk?: string;
}

interface FloodZoneEnrichmentProps {
  data: FloodZoneData;
  cached?: boolean;
}

export const FloodZoneEnrichment = ({
  data,
  cached,
}: FloodZoneEnrichmentProps) => {
  return (
    <EnrichmentCard
      title="Flood Zone Information"
      icon={Droplets}
      cached={cached}
    >
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Flood Zone
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.flood_zone || "N/A"}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Flood Risk
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.flood_risk || "N/A"}
          </Typography>
        </Grid>
      </Grid>
    </EnrichmentCard>
  );
};
