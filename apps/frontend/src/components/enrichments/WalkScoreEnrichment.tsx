import { Grid, Typography } from "@mui/material";
import { Map } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface WalkScoreData {
  walk_score?: number;
  bike_score?: number;
  transit_score?: number;
  description?: string;
}

interface WalkScoreEnrichmentProps {
  data: WalkScoreData;
  cached?: boolean;
}

export const WalkScoreEnrichment = ({
  data,
  cached,
}: WalkScoreEnrichmentProps) => {
  return (
    <EnrichmentCard title="Walkability Scores" icon={Map} cached={cached}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Walk Score
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.walk_score || "N/A"}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Bike Score
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.bike_score || "N/A"}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Transit Score
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.transit_score || "N/A"}
          </Typography>
        </Grid>
        {data.description && (
          <Grid size={{ xs: 12 }}>
            <Typography variant="body2" color="text.secondary">
              {data.description}
            </Typography>
          </Grid>
        )}
      </Grid>
    </EnrichmentCard>
  );
};
