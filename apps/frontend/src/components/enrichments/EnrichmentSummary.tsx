import { Card, CardContent, Typography, Grid } from "@mui/material";
import { EnrichmentData } from "@/types";

interface EnrichmentSummaryProps {
  enrichment: EnrichmentData;
}

export const EnrichmentSummary = ({ enrichment }: EnrichmentSummaryProps) => {
  if (!enrichment.metadata) return null;

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" fontWeight="600" gutterBottom>
          Enrichment Summary
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Providers Run
            </Typography>
            <Typography variant="h6">
              {enrichment.metadata.successful_providers}/
              {enrichment.metadata.total_providers}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              API Calls
            </Typography>
            <Typography variant="h6">
              {enrichment.metadata.total_api_calls}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Cached Results
            </Typography>
            <Typography variant="h6">
              {enrichment.metadata.cached_providers}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Failed
            </Typography>
            <Typography variant="h6">
              {enrichment.metadata.failed_providers}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};
