import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, MapPin, AlertCircle } from "lucide-react";
import {
  Card,
  CardContent,
  Box,
  Typography,
  TextField,
  Button,
  Alert,
  AlertTitle,
  InputAdornment,
} from "@mui/material";
import { propertiesApi } from "@/api/properties";
import { savedPropertiesApi } from "@/api/savedProperties";
import { Property } from "@/types";
import { PropertyCard } from "@/components/property/PropertyCard";
import { LoadingSpinner } from "@/components/layout";

export const PropertySearchPage = () => {
  const navigate = useNavigate();
  const [address, setAddress] = useState("");
  const [property, setProperty] = useState<Property | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaved, setIsSaved] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!address.trim()) {
      setError("Please enter an address");
      return;
    }

    setIsLoading(true);
    setError(null);
    setProperty(null);

    try {
      const response = await propertiesApi.search({ address: address.trim() });

      if (response.success && response.property) {
        setProperty(response.property);
        // Check if property is already saved
        // Note: In a real app, you'd check this against saved properties
        setIsSaved(false);
      } else {
        setError(response.message || "Property not found");
      }
    } catch (err) {
      console.error("Search error:", err);
      setError(
        err.response?.data?.detail ||
          "Failed to search property. Please check the address and try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveProperty = async (prop: Property) => {
    try {
      await savedPropertiesApi.save({
        property_id: prop.id,
        is_favorite: false,
      });
      setIsSaved(true);
    } catch (err) {
      console.error("Save error:", err);
      setError(err.response?.data?.detail || "Failed to save property");
    }
  };

  const handleViewDetails = (prop: Property) => {
    navigate(`/properties/${prop.id}`);
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page Header */}
      <Box>
        <Typography variant="h3" fontWeight="bold" color="text.primary">
          Search Properties
        </Typography>
        <Typography color="text.secondary" mt={1}>
          Find and analyze residential properties by address
        </Typography>
      </Box>

      {/* Search Form */}
      <Card>
        <CardContent>
          <form onSubmit={handleSearch}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <TextField
                fullWidth
                placeholder="Enter full address (e.g., 123 Main St, Seattle, WA 98101)"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                disabled={isLoading}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <MapPin size={20} />
                    </InputAdornment>
                  ),
                }}
              />
              <Button
                type="submit"
                variant="contained"
                size="large"
                startIcon={<Search size={20} />}
                disabled={isLoading || !address.trim()}
                fullWidth
              >
                {isLoading ? "Searching..." : "Search Property"}
              </Button>
            </Box>
          </form>

          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              💡 Tip: Include street number, street name, city, state, and ZIP
              code for best results.
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && (
        <Box sx={{ py: 6 }}>
          <LoadingSpinner text="Searching for property..." />
        </Box>
      )}

      {/* Search Results */}
      {!isLoading && property && (
        <Box>
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 3,
            }}
          >
            <Typography variant="h5" fontWeight="600">
              Search Results
            </Typography>
            <Button
              variant="outlined"
              onClick={() => handleViewDetails(property)}
            >
              View Full Details
            </Button>
          </Box>
          <Box sx={{ maxWidth: 600 }}>
            <PropertyCard
              property={property}
              onSave={handleSaveProperty}
              isSaved={isSaved}
              showActions={true}
            />
          </Box>
        </Box>
      )}

      {/* Info Card */}
      {!property && !isLoading && (
        <Card
          sx={{
            bgcolor: "primary.50",
            border: "1px solid",
            borderColor: "primary.200",
          }}
        >
          <CardContent>
            <Box sx={{ display: "flex", alignItems: "start", gap: 2 }}>
              <Box
                sx={{
                  bgcolor: "primary.100",
                  borderRadius: 2,
                  p: 1,
                  display: "flex",
                }}
              >
                <AlertCircle size={20} color="#1976d2" />
              </Box>
              <Box>
                <Typography variant="subtitle1" fontWeight="600" gutterBottom>
                  How Property Search Works
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Enter a complete address to search for property information.
                  Once found, you can:
                </Typography>
                <Box component="ul" sx={{ m: 0, pl: 2 }}>
                  <Typography
                    component="li"
                    variant="body2"
                    color="text.secondary"
                  >
                    View basic property details (beds, baths, square footage)
                  </Typography>
                  <Typography
                    component="li"
                    variant="body2"
                    color="text.secondary"
                  >
                    Save properties to your favorites
                  </Typography>
                  <Typography
                    component="li"
                    variant="body2"
                    color="text.secondary"
                  >
                    Access detailed analysis with walk scores and nearby
                    amenities
                  </Typography>
                  <Typography
                    component="li"
                    variant="body2"
                    color="text.secondary"
                  >
                    Calculate distances to your custom locations
                  </Typography>
                </Box>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};
