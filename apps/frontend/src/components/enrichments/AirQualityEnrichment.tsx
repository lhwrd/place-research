import { Grid, Typography, Chip } from "@mui/material";
import { Wind } from "lucide-react";
import { EnrichmentCard } from "./EnrichmentCard";

interface AirQualityData {
  AQI: number;
  Category?: {
    Name?: string;
  };
  ParameterName: string;
  ReportingArea: string;
}

interface AirQualityEnrichmentProps {
  data: AirQualityData;
  cached?: boolean;
}

export const AirQualityEnrichment = ({
  data,
  cached,
}: AirQualityEnrichmentProps) => {
  return (
    <EnrichmentCard title="Air Quality" icon={Wind} cached={cached}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Air Quality Index (AQI)
          </Typography>
          <Typography variant="h4" fontWeight="600" color="primary">
            {data.AQI}
          </Typography>
          <Chip
            label={data.Category?.Name || "Unknown"}
            color={
              data.AQI <= 50 ? "success" : data.AQI <= 100 ? "warning" : "error"
            }
            size="small"
            sx={{ mt: 1 }}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Primary Pollutant
          </Typography>
          <Typography variant="body1">{data.ParameterName}</Typography>
          <Typography variant="caption" color="text.secondary">
            {data.ReportingArea}
          </Typography>
        </Grid>
      </Grid>
    </EnrichmentCard>
  );
};
