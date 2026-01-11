import { Building2 } from "lucide-react";
import { Card, CardContent, Box, Typography } from "@mui/material";

export const PropertyDetailPage = () => {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page Header */}
      <Box>
        <Typography variant="h3" fontWeight="bold" color="text.primary">
          Property Details
        </Typography>
        <Typography color="text.secondary" mt={1}>
          View detailed property information
        </Typography>
      </Box>

      {/* Content Card */}
      <Card>
        <CardContent>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <Building2 style={{ width: 20, height: 20, color: "#757575" }} />
            <Typography variant="h6" fontWeight="600">
              Coming Soon
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" mb={2}>
            This feature is under development
          </Typography>
          <Typography color="text.secondary">
            Soon you'll be able to view comprehensive property details including
            enriched data from multiple sources.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};
