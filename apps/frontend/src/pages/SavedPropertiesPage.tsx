import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Heart, Search, Star, Archive } from "lucide-react";
import {
  Card,
  CardContent,
  Button,
  Chip,
  Box,
  Typography,
  Tabs,
  Tab,
  Alert,
  AlertTitle,
} from "@mui/material";
import { savedPropertiesApi } from "@/api/savedProperties";
import { SavedProperty } from "@/types";
import { PropertyList } from "@/components/property/PropertyList";
import { LoadingSpinner } from "@/components/layout";

type TabType = "all" | "favorites" | "archived";

export const SavedPropertiesPage = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>("all");
  const [savedProperties, setSavedProperties] = useState<SavedProperty[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [counts, setCounts] = useState({
    all: 0,
    favorites: 0,
    archived: 0,
  });

  // Fetch saved properties
  const fetchSavedProperties = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const filters: Record<string, boolean> = {};

      if (activeTab === "favorites") {
        filters.is_favorite = true;
        filters.is_archived = false;
      } else if (activeTab === "archived") {
        filters.is_archived = true;
      } else {
        // All tab: show non-archived properties
        filters.is_archived = false;
      }

      const response = await savedPropertiesApi.getAll(0, 100, filters);
      setSavedProperties(response.items);

      // Update counts (we'll fetch each separately to get accurate counts)
      const [allResponse, favoritesResponse, archivedResponse] =
        await Promise.all([
          savedPropertiesApi.getAll(0, 1, { is_archived: false }),
          savedPropertiesApi.getAll(0, 1, {
            is_favorite: true,
            is_archived: false,
          }),
          savedPropertiesApi.getAll(0, 1, { is_archived: true }),
        ]);

      setCounts({
        all: allResponse.total,
        favorites: favoritesResponse.total,
        archived: archivedResponse.total,
      });
    } catch (err) {
      console.error("Error fetching saved properties:", err);
      setError(err.response?.data?.detail || "Failed to load saved properties");
    } finally {
      setIsLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    fetchSavedProperties();
  }, [fetchSavedProperties]);

  // Handle removing a saved property
  const handleRemoveProperty = async (propertyId: number) => {
    try {
      const savedProperty = savedProperties.find(
        (sp) => sp.property.id === propertyId
      );
      if (!savedProperty) return;

      await savedPropertiesApi.delete(savedProperty.id);

      // Refresh the list
      await fetchSavedProperties();
    } catch (err) {
      console.error("Error removing saved property:", err);
      setError(err.response?.data?.detail || "Failed to remove property");
    }
  };

  const tabs = [
    {
      id: "all" as TabType,
      label: "All Properties",
      count: counts.all,
      icon: Heart,
    },
    {
      id: "favorites" as TabType,
      label: "Favorites",
      count: counts.favorites,
      icon: Star,
    },
    {
      id: "archived" as TabType,
      label: "Archived",
      count: counts.archived,
      icon: Archive,
    },
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

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs
          value={tabs.findIndex((t) => t.id === activeTab)}
          onChange={(_, newValue) => setActiveTab(tabs[newValue].id)}
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <Tab
                key={tab.id}
                label={
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Icon size={16} />
                    {tab.label}
                    <Chip label={tab.count} size="small" />
                  </Box>
                }
              />
            );
          })}
        </Tabs>
      </Box>

      {/* Loading State */}
      {isLoading ? (
        <Box sx={{ py: 8 }}>
          <LoadingSpinner text="Loading saved properties..." />
        </Box>
      ) : savedProperties.length === 0 ? (
        /* Empty State */
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
                {activeTab === "favorites"
                  ? "No favorite properties yet"
                  : activeTab === "archived"
                  ? "No archived properties"
                  : "No saved properties yet"}
              </Typography>
              <Typography
                color="text.secondary"
                mb={3}
                sx={{ maxWidth: 400, mx: "auto" }}
              >
                {activeTab === "favorites"
                  ? "Mark properties as favorites to see them here."
                  : activeTab === "archived"
                  ? "Archived properties will appear here."
                  : "Start searching for properties and save the ones you like to see them here."}
              </Typography>
              <Button
                variant="contained"
                startIcon={<Search size={16} />}
                onClick={() => navigate("/search")}
              >
                Search Properties
              </Button>
            </Box>
          </CardContent>
        </Card>
      ) : (
        /* Properties List */
        <PropertyList
          properties={savedProperties.map((sp) => sp.property)}
          onRemoveProperty={(property) => handleRemoveProperty(property.id)}
          savedPropertyIds={savedProperties.map((sp) => sp.property.id)}
          emptyMessage="No properties found"
          className="w-full"
        />
      )}
    </Box>
  );
};
