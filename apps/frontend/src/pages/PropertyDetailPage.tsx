import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { MapPin, Heart, ArrowLeft, Sparkles } from "lucide-react";
import {
  Card,
  CardContent,
  Box,
  Typography,
  Button,
  Alert,
  AlertTitle,
  CircularProgress,
} from "@mui/material";
import { propertiesApi } from "@/api/properties";
import { savedPropertiesApi } from "@/api/savedProperties";
import { Property, EnrichmentData } from "@/types";
import { LoadingSpinner } from "@/components/layout";
import { PropertyOverview, PropertyDetailsCard } from "@/components/property";
import {
  getEnrichmentComponents,
  EnrichmentSummary,
} from "@/components/enrichments";
import axios from "axios";

export const PropertyDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [property, setProperty] = useState<Property | null>(null);
  const [enrichment, setEnrichment] = useState<EnrichmentData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEnriching, setIsEnriching] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProperty = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await propertiesApi.getById(Number(id));
      if (response.success && response.property) {
        setProperty(response.property);
      } else {
        setError("Property not found");
      }
    } catch (err: unknown) {
      console.error("Error fetching property:", err);
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.detail || "Failed to load property details"
        );
      } else {
        setError("Failed to load property details");
      }
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) {
      fetchProperty();
    }
  }, [id, fetchProperty]);

  // fetchProperty is now wrapped in useCallback above

  const handleEnrich = async () => {
    if (!property) return;

    setIsEnriching(true);
    setError(null);

    try {
      const response = await propertiesApi.enrich(property.id, true);
      if (response.success && response.enrichment) {
        setEnrichment(response.enrichment);
        console.log("Enrichment data received:", response.enrichment);
        console.log(
          "Provider names:",
          Object.keys(response.enrichment.enrichment_data || {})
        );
        // Log each provider's data
        Object.entries(response.enrichment.enrichment_data || {}).forEach(
          ([key, value]: [
            string,
            { success: boolean; cached?: boolean; data?: unknown }
          ]) => {
            console.log(`Provider: ${key}`, {
              success: value.success,
              cached: value.cached,
              hasData: !!value.data,
              data: value.data,
            });
          }
        );
      }
    } catch (err: unknown) {
      console.error("Error enriching property:", err);
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.detail ||
            "Failed to enrich property. You may have reached your rate limit."
        );
      } else {
        setError(
          "Failed to enrich property. You may have reached your rate limit."
        );
      }
    } finally {
      setIsEnriching(false);
    }
  };

  const handleSaveProperty = async () => {
    if (!property) return;

    try {
      await savedPropertiesApi.save({
        property_id: property.id,
        is_favorite: false,
      });
      setIsSaved(true);
    } catch (err: unknown) {
      console.error("Save error:", err);
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Failed to save property");
      } else {
        setError("Failed to save property");
      }
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ py: 8 }}>
        <LoadingSpinner text="Loading property details..." />
      </Box>
    );
  }

  if (error && !property) {
    return (
      <Box>
        <Alert severity="error">
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
        <Button
          startIcon={<ArrowLeft size={16} />}
          onClick={() => navigate("/search")}
          sx={{ mt: 2 }}
        >
          Back to Search
        </Button>
      </Box>
    );
  }

  if (!property) {
    return null;
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Back Button */}
      <Button
        startIcon={<ArrowLeft size={16} />}
        onClick={() => navigate(-1)}
        sx={{ alignSelf: "flex-start" }}
      >
        Back
      </Button>

      {/* Page Header */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "start",
        }}
      >
        <Box>
          <Typography variant="h3" fontWeight="bold" color="text.primary">
            {property.address}
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1 }}>
            <MapPin size={16} />
            <Typography color="text.secondary">
              {property.city}, {property.state} {property.zip_code}
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            variant={isSaved ? "outlined" : "contained"}
            startIcon={<Heart size={16} />}
            onClick={handleSaveProperty}
            disabled={isSaved}
          >
            {isSaved ? "Saved" : "Save Property"}
          </Button>
          <Button
            variant="outlined"
            startIcon={
              isEnriching ? (
                <CircularProgress size={16} />
              ) : (
                <Sparkles size={16} />
              )
            }
            onClick={handleEnrich}
            disabled={isEnriching}
          >
            {isEnriching ? "Enriching..." : "Enrich Data"}
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
      )}

      {/* Property Overview */}
      <PropertyOverview property={property} />

      {/* Property Details */}
      <PropertyDetailsCard property={property} />

      {/* Enrichment Data */}
      {enrichment && enrichment.success && enrichment.enrichment_data && (
        <>
          {/* Render all enrichment components from registry */}
          {getEnrichmentComponents(enrichment.enrichment_data)}

          {/* Enrichment Summary */}
          <EnrichmentSummary enrichment={enrichment} />
        </>
      )}

      {/* Enrich CTA */}
      {!enrichment && !isEnriching && (
        <Card
          sx={{
            bgcolor: "primary.50",
            border: "1px solid",
            borderColor: "primary.200",
          }}
        >
          <CardContent>
            <Box sx={{ textAlign: "center", py: 3 }}>
              <Sparkles
                size={32}
                color="#1976d2"
                style={{ marginBottom: 16 }}
              />
              <Typography variant="h6" fontWeight="600" gutterBottom>
                Get Enriched Property Data
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Click "Enrich Data" to get walk scores, nearby amenities, and
                distances to your custom locations.
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};
