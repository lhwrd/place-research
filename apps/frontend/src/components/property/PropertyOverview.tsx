import { Card, CardContent, Box, Typography, Grid } from "@mui/material";
import { DollarSign, Bed, Bath, Maximize } from "lucide-react";
import { Property } from "@/types";

interface PropertyOverviewProps {
  property: Property;
}

const formatCurrency = (value: number | null) => {
  if (!value) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
};

const formatNumber = (value: number | null) => {
  if (!value) return "N/A";
  return new Intl.NumberFormat("en-US").format(value);
};

export const PropertyOverview = ({ property }: PropertyOverviewProps) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h5" fontWeight="600" gutterBottom>
          Property Overview
        </Typography>
        <Grid container spacing={3} sx={{ mt: 1 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
              <DollarSign size={20} color="#666" />
              <Typography variant="body2" color="text.secondary">
                Estimated Value
              </Typography>
            </Box>
            <Typography variant="h6" fontWeight="600">
              {formatCurrency(property.estimated_value)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
              <Bed size={20} color="#666" />
              <Typography variant="body2" color="text.secondary">
                Bedrooms
              </Typography>
            </Box>
            <Typography variant="h6" fontWeight="600">
              {property.bedrooms || "N/A"}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
              <Bath size={20} color="#666" />
              <Typography variant="body2" color="text.secondary">
                Bathrooms
              </Typography>
            </Box>
            <Typography variant="h6" fontWeight="600">
              {property.bathrooms || "N/A"}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
              <Maximize size={20} color="#666" />
              <Typography variant="body2" color="text.secondary">
                Square Feet
              </Typography>
            </Box>
            <Typography variant="h6" fontWeight="600">
              {formatNumber(property.square_feet)}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};
