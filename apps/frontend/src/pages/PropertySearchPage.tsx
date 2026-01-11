import { Search } from "lucide-react";
import { Card, CardContent, Box, Typography } from "@mui/material";

export const PropertySearchPage = () => {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page Header */}
      <Box>
        <Typography variant="h3" fontWeight="bold" color="text.primary">
          Search Properties
        </Typography>
        <Typography color="text.secondary" mt={1}>
          Find your dream home
        </Typography>
      </Box>

      {/* Content Card */}
      <Card>
        <CardContent>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <Search style={{ width: 20, height: 20, color: "#757575" }} />
            <Typography variant="h6" fontWeight="600">
              Coming Soon
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" mb={2}>
            This feature is under development
          </Typography>
          <Typography color="text.secondary">
            Soon you'll be able to search for residential properties and access
            enriched data.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};
