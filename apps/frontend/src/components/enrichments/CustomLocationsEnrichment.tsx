import { Grid, Typography, Card, CardContent } from "@mui/material";
import { Navigation } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface DistanceLocation {
  location_id: number;
  location_name: string;
  distance_miles?: number;
  duration_minutes?: number;
  duration_in_traffic_minutes?: number;
}

interface CustomLocationsData {
  distances: DistanceLocation[];
}

interface CustomLocationsEnrichmentProps {
  data: CustomLocationsData;
  cached?: boolean;
}

export const CustomLocationsEnrichment = ({
  data,
  cached,
}: CustomLocationsEnrichmentProps) => {
  return (
    <EnrichmentCard
      title="Distances to Your Locations"
      icon={Navigation}
      cached={cached}
    >
      <Grid container spacing={2} sx={{ mt: 1 }}>
        {data.distances.map((location) => (
          <Grid size={{ xs: 12, sm: 6 }} key={location.location_id}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle2" fontWeight="600" gutterBottom>
                  {location.location_name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {location.distance_miles?.toFixed(2) || "N/A"} miles •{" "}
                  {location.duration_minutes || "N/A"} min drive
                </Typography>
                {location.duration_in_traffic_minutes && (
                  <Typography variant="caption" color="text.secondary">
                    ({location.duration_in_traffic_minutes} min with traffic)
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </EnrichmentCard>
  );
};
