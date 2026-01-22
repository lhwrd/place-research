import {
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Divider,
} from "@mui/material";
import { Property } from "@/types";

interface PropertyDetailsCardProps {
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

export const PropertyDetailsCard = ({ property }: PropertyDetailsCardProps) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h5" fontWeight="600" gutterBottom>
          Property Details
        </Typography>
        <Grid container spacing={3} sx={{ mt: 1 }}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Property Type
            </Typography>
            <Chip label={property.property_type || "Unknown"} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Year Built
            </Typography>
            <Typography variant="body1">
              {property.year_built || "N/A"}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Lot Size
            </Typography>
            <Typography variant="body1">
              {property.lot_size
                ? `${formatNumber(property.lot_size)} sqft`
                : "N/A"}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              County
            </Typography>
            <Typography variant="body1">{property.county || "N/A"}</Typography>
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" fontWeight="600" gutterBottom>
          Financial Information
        </Typography>
        <Grid container spacing={3} sx={{ mt: 1 }}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Last Sold Price
            </Typography>
            <Typography variant="body1">
              {formatCurrency(property.last_sold_price)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Last Sold Date
            </Typography>
            <Typography variant="body1">
              {property.last_sold_date
                ? new Date(property.last_sold_date).toLocaleDateString()
                : "N/A"}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Tax Assessed Value
            </Typography>
            <Typography variant="body1">
              {formatCurrency(property.tax_assessed_value)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Annual Tax
            </Typography>
            <Typography variant="body1">
              {formatCurrency(property.annual_tax)}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};
