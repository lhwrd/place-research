import { Grid, Typography, Chip } from "@mui/material";
import { Truck } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface HighwayData {
  highway_distance_m: number;
  nearest_highway_type: string;
  road_noise_level_db: number;
  road_noise_category: string;
}

interface RailroadData {
  railroad_distance_m: number;
}

interface TransportationEnrichmentProps {
  highwayData?: HighwayData;
  railroadData?: RailroadData;
  highwayCached?: boolean;
  railroadCached?: boolean;
}

export const TransportationEnrichment = ({
  highwayData,
  railroadData,
  highwayCached,
  railroadCached,
}: TransportationEnrichmentProps) => {
  const cached = highwayCached || railroadCached;

  return (
    <EnrichmentCard
      title="Transportation Infrastructure"
      icon={Truck}
      cached={cached}
    >
      <Grid container spacing={3}>
        {highwayData && (
          <>
            <Grid size={{ xs: 12, sm: 6 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Highway Distance
              </Typography>
              <Typography variant="body1">
                {(highwayData.highway_distance_m * 3.28084).toFixed(0)} feet
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {highwayData.nearest_highway_type}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Road Noise Level
              </Typography>
              <Typography variant="body1">
                {highwayData.road_noise_level_db} dB
              </Typography>
              <Chip
                label={highwayData.road_noise_category}
                color={
                  highwayData.road_noise_category === "Low"
                    ? "success"
                    : highwayData.road_noise_category === "Medium"
                    ? "warning"
                    : "error"
                }
                size="small"
                sx={{ mt: 0.5 }}
              />
            </Grid>
          </>
        )}
        {railroadData && (
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Railroad Distance
            </Typography>
            <Typography variant="body1">
              {((railroadData.railroad_distance_m * 3.28084) / 5280).toFixed(2)}{" "}
              miles
            </Typography>
          </Grid>
        )}
      </Grid>
    </EnrichmentCard>
  );
};
