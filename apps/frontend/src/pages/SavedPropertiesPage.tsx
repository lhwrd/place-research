import { useState } from "react";
import { Heart, Search } from "lucide-react";
import {
  Card,
  CardContent,
  Button,
  Chip,
  Box,
  Typography,
  Tabs,
  Tab,
} from "@mui/material";

export const SavedPropertiesPage = () => {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    { id: 0, label: "All Properties", count: 12 },
    { id: 1, label: "Favorites", count: 5 },
    { id: 2, label: "Archived", count: 3 },
  ];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page Header */}
      <Box>
        <Typography variant="h3" fontWeight="bold" color="text.primary">
          Saved Properties
        </Typography>
        <Typography color="text.secondary" mt={1}>
          Manage your favorite properties and compare them
        </Typography>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
        >
          {tabs.map((tab) => (
            <Tab
              key={tab.id}
              label={
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  {tab.label}
                  <Chip label={tab.count} size="small" />
                </Box>
              }
            />
          ))}
        </Tabs>
      </Box>

      {/* Empty State */}
      <Card>
        <CardContent sx={{ py: 6 }}>
          <Box sx={{ textAlign: "center", py: 6 }}>
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 64,
                height: 64,
                bgcolor: "grey.100",
                borderRadius: "50%",
                mb: 2,
              }}
            >
              <Heart style={{ width: 32, height: 32, color: "#bdbdbd" }} />
            </Box>
            <Typography
              variant="h6"
              fontWeight="600"
              color="text.primary"
              mb={1}
            >
              No saved properties yet
            </Typography>
            <Typography
              color="text.secondary"
              mb={3}
              sx={{ maxWidth: 400, mx: "auto" }}
            >
              Start searching for properties and save the ones you like to see
              them here.
            </Typography>
            <Button variant="contained" startIcon={<Search size={16} />}>
              Search Properties
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};
