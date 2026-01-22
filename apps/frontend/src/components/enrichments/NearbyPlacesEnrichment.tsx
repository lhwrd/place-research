import { Grid, Typography } from "@mui/material";
import { MapPin } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";
import { NearbyPlace } from "@/types";

interface NearbyPlacesData {
  places_nearby: NearbyPlace[];
}

interface NearbyPlacesEnrichmentProps {
  data: NearbyPlacesData;
  cached?: boolean;
}

export const NearbyPlacesEnrichment = ({
  data,
  cached,
}: NearbyPlacesEnrichmentProps) => {
  return (
    <EnrichmentCard title="Nearby Places" icon={MapPin} cached={cached}>
      <Grid container spacing={2} sx={{ mt: 1 }}>
        {data.places_nearby.map((place, index) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={index}>
            <Typography variant="body2" fontWeight="bold">
              {place.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {place.type}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {place.distance_miles !== null &&
              place.distance_miles !== undefined
                ? `${place.distance_miles} mi`
                : "N/A"}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {place.rating !== null && place.rating !== undefined
                ? place.rating
                : "N/A"}
            </Typography>
          </Grid>
        ))}
      </Grid>
    </EnrichmentCard>
  );
};
