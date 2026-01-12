import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Building2,
  MapPin,
  Bed,
  Bath,
  Maximize,
  Calendar,
  DollarSign,
  TrendingUp,
  Heart,
  ArrowLeft,
  Sparkles,
  Map,
  Star,
} from "lucide-react";
import {
  Card,
  CardContent,
  Box,
  Typography,
  Button,
  Chip,
  Grid,
  Alert,
  AlertTitle,
  Divider,
  CircularProgress,
} from "@mui/material";
import { propertiesApi } from "@/api/properties";
import { savedPropertiesApi } from "@/api/savedProperties";
import { Property, EnrichmentData } from "@/types";
import { LoadingSpinner } from "@/components/layout";

export const PropertyDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [property, setProperty] = useState<Property | null>(null);
  const [enrichment, setEnrichment] = useState<EnrichmentData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEnriching, setIsEnriching] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      fetchProperty();
    }
  }, [id]);

  const fetchProperty = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await propertiesApi.getById(Number(id));
      if (response.success && response.property) {
        setProperty(response.property);
      } else {
        setError("Property not found");
      }
    } catch (err: any) {
      console.error("Error fetching property:", err);
      setError(err.response?.data?.detail || "Failed to load property details");
    } finally {
      setIsLoading(false);
    }
  };

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
          ([key, value]: [string, any]) => {
            console.log(`Provider: ${key}`, {
              success: value.success,
              cached: value.cached,
              hasData: !!value.data,
              data: value.data,
            });
          }
        );
      }
    } catch (err: any) {
      console.error("Error enriching property:", err);
      setError(
        err.response?.data?.detail ||
          "Failed to enrich property. You may have reached your rate limit."
      );
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
    } catch (err: any) {
      console.error("Save error:", err);
      setError(err.response?.data?.detail || "Failed to save property");
    }
  };

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
      <Card>
        <CardContent>
          <Typography variant="h5" fontWeight="600" gutterBottom>
            Property Overview
          </Typography>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Box
                sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}
              >
                <DollarSign size={20} color="#666" />
                <Typography variant="body2" color="text.secondary">
                  Estimated Value
                </Typography>
              </Box>
              <Typography variant="h6" fontWeight="600">
                {formatCurrency(property.estimated_value)}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box
                sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}
              >
                <Bed size={20} color="#666" />
                <Typography variant="body2" color="text.secondary">
                  Bedrooms
                </Typography>
              </Box>
              <Typography variant="h6" fontWeight="600">
                {property.bedrooms || "N/A"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box
                sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}
              >
                <Bath size={20} color="#666" />
                <Typography variant="body2" color="text.secondary">
                  Bathrooms
                </Typography>
              </Box>
              <Typography variant="h6" fontWeight="600">
                {property.bathrooms || "N/A"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box
                sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}
              >
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

      {/* Property Details */}
      <Card>
        <CardContent>
          <Typography variant="h5" fontWeight="600" gutterBottom>
            Property Details
          </Typography>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Property Type
              </Typography>
              <Chip label={property.property_type || "Unknown"} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Year Built
              </Typography>
              <Typography variant="body1">
                {property.year_built || "N/A"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Lot Size
              </Typography>
              <Typography variant="body1">
                {property.lot_size
                  ? `${formatNumber(property.lot_size)} sqft`
                  : "N/A"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                County
              </Typography>
              <Typography variant="body1">
                {property.county || "N/A"}
              </Typography>
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" fontWeight="600" gutterBottom>
            Financial Information
          </Typography>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Last Sold Price
              </Typography>
              <Typography variant="body1">
                {formatCurrency(property.last_sold_price)}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Last Sold Date
              </Typography>
              <Typography variant="body1">
                {property.last_sold_date
                  ? new Date(property.last_sold_date).toLocaleDateString()
                  : "N/A"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Tax Assessed Value
              </Typography>
              <Typography variant="body1">
                {formatCurrency(property.tax_assessed_value)}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
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

      {/* Enrichment Data */}
      {enrichment && enrichment.success && (
        <>
          {/* Walk Scores */}
          {enrichment.enrichment_data?.walkscore_provider?.success &&
            enrichment.enrichment_data.walkscore_provider.data && (
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Map size={20} />
                    <Typography variant="h5" fontWeight="600">
                      Walkability Scores
                    </Typography>
                    {enrichment.enrichment_data.walkscore_provider.cached && (
                      <Chip label="Cached" size="small" color="info" />
                    )}
                  </Box>
                  <Grid container spacing={3}>
                    <Grid item xs={12} sm={4}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Walk Score
                      </Typography>
                      <Typography variant="h4" fontWeight="600" color="primary">
                        {enrichment.enrichment_data.walkscore_provider.data
                          .walk_score || "N/A"}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Bike Score
                      </Typography>
                      <Typography variant="h4" fontWeight="600" color="primary">
                        {enrichment.enrichment_data.walkscore_provider.data
                          .bike_score || "N/A"}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Transit Score
                      </Typography>
                      <Typography variant="h4" fontWeight="600" color="primary">
                        {enrichment.enrichment_data.walkscore_provider.data
                          .transit_score || "N/A"}
                      </Typography>
                    </Grid>
                    {enrichment.enrichment_data.walkscore_provider.data
                      .description && (
                      <Grid item xs={12}>
                        <Typography variant="body2" color="text.secondary">
                          {
                            enrichment.enrichment_data.walkscore_provider.data
                              .description
                          }
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </CardContent>
              </Card>
            )}

          {/* Air Quality */}
          {enrichment.enrichment_data?.air_quality_provider?.success &&
            enrichment.enrichment_data.air_quality_provider.data && (
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Typography variant="h5" fontWeight="600">
                      Air Quality
                    </Typography>
                    {enrichment.enrichment_data.air_quality_provider.cached && (
                      <Chip label="Cached" size="small" color="info" />
                    )}
                  </Box>
                  <Grid container spacing={3}>
                    <Grid item xs={12} sm={6}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Air Quality Index (AQI)
                      </Typography>
                      <Typography variant="h4" fontWeight="600" color="primary">
                        {
                          enrichment.enrichment_data.air_quality_provider.data
                            .AQI
                        }
                      </Typography>
                      <Chip
                        label={
                          enrichment.enrichment_data.air_quality_provider.data
                            .Category?.Name || "Unknown"
                        }
                        color={
                          enrichment.enrichment_data.air_quality_provider.data
                            .AQI <= 50
                            ? "success"
                            : enrichment.enrichment_data.air_quality_provider
                                .data.AQI <= 100
                            ? "warning"
                            : "error"
                        }
                        size="small"
                        sx={{ mt: 1 }}
                      />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Primary Pollutant
                      </Typography>
                      <Typography variant="body1">
                        {
                          enrichment.enrichment_data.air_quality_provider.data
                            .ParameterName
                        }
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {
                          enrichment.enrichment_data.air_quality_provider.data
                            .ReportingArea
                        }
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            )}

          {/* Climate */}
          {enrichment.enrichment_data?.annual_average_climate_provider
            ?.success &&
            enrichment.enrichment_data.annual_average_climate_provider.data && (
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Typography variant="h5" fontWeight="600">
                      Annual Climate Averages
                    </Typography>
                    {enrichment.enrichment_data.annual_average_climate_provider
                      .cached && (
                      <Chip label="Cached" size="small" color="info" />
                    )}
                  </Box>
                  <Grid container spacing={3}>
                    <Grid item xs={12} sm={6}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Average Temperature
                      </Typography>
                      <Typography variant="h4" fontWeight="600" color="primary">
                        {enrichment.enrichment_data.annual_average_climate_provider.data.annual_average_temperature?.toFixed(
                          1
                        )}
                        °F
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Average Precipitation
                      </Typography>
                      <Typography variant="h4" fontWeight="600" color="primary">
                        {enrichment.enrichment_data.annual_average_climate_provider.data.annual_average_precipitation?.toFixed(
                          2
                        )}
                        "
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            )}

          {/* Flood Zone */}
          {enrichment.enrichment_data?.flood_zone_provider?.success &&
            enrichment.enrichment_data.flood_zone_provider.data?.result && (
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Typography variant="h5" fontWeight="600">
                      Flood Zone Information
                    </Typography>
                    {enrichment.enrichment_data.flood_zone_provider.cached && (
                      <Chip label="Cached" size="small" color="info" />
                    )}
                  </Box>
                  <Grid container spacing={3}>
                    {enrichment.enrichment_data.flood_zone_provider.data.result[
                      "flood.s_fld_haz_ar"
                    ]?.[0] && (
                      <>
                        <Grid item xs={12} sm={6}>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            gutterBottom
                          >
                            Flood Zone
                          </Typography>
                          <Typography
                            variant="h4"
                            fontWeight="600"
                            color="primary"
                          >
                            {
                              enrichment.enrichment_data.flood_zone_provider
                                .data.result["flood.s_fld_haz_ar"][0].fld_zone
                            }
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {
                              enrichment.enrichment_data.flood_zone_provider
                                .data.result["flood.s_fld_haz_ar"][0].zone_subty
                            }
                          </Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            gutterBottom
                          >
                            In Special Flood Hazard Area
                          </Typography>
                          <Chip
                            label={
                              enrichment.enrichment_data.flood_zone_provider
                                .data.result["flood.s_fld_haz_ar"][0]
                                .sfha_tf === "T"
                                ? "Yes"
                                : "No"
                            }
                            color={
                              enrichment.enrichment_data.flood_zone_provider
                                .data.result["flood.s_fld_haz_ar"][0]
                                .sfha_tf === "T"
                                ? "warning"
                                : "success"
                            }
                          />
                        </Grid>
                      </>
                    )}
                  </Grid>
                </CardContent>
              </Card>
            )}

          {/* Highway & Railroad Noise */}
          {(enrichment.enrichment_data?.highway_provider?.success ||
            enrichment.enrichment_data?.railroad_provider?.success) && (
            <Card>
              <CardContent>
                <Typography variant="h5" fontWeight="600" gutterBottom>
                  Transportation Infrastructure
                </Typography>
                <Grid container spacing={3} sx={{ mt: 1 }}>
                  {enrichment.enrichment_data?.highway_provider?.success &&
                    enrichment.enrichment_data.highway_provider.data && (
                      <>
                        <Grid item xs={12} sm={6}>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            gutterBottom
                          >
                            Highway Distance
                          </Typography>
                          <Typography variant="body1">
                            {(
                              enrichment.enrichment_data.highway_provider.data
                                .highway_distance_m * 3.28084
                            ).toFixed(0)}{" "}
                            feet
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {
                              enrichment.enrichment_data.highway_provider.data
                                .nearest_highway_type
                            }
                          </Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            gutterBottom
                          >
                            Road Noise Level
                          </Typography>
                          <Typography variant="body1">
                            {
                              enrichment.enrichment_data.highway_provider.data
                                .road_noise_level_db
                            }{" "}
                            dB
                          </Typography>
                          <Chip
                            label={
                              enrichment.enrichment_data.highway_provider.data
                                .road_noise_category
                            }
                            color={
                              enrichment.enrichment_data.highway_provider.data
                                .road_noise_category === "Low"
                                ? "success"
                                : enrichment.enrichment_data.highway_provider
                                    .data.road_noise_category === "Medium"
                                ? "warning"
                                : "error"
                            }
                            size="small"
                            sx={{ mt: 0.5 }}
                          />
                        </Grid>
                      </>
                    )}
                  {enrichment.enrichment_data?.railroad_provider?.success &&
                    enrichment.enrichment_data.railroad_provider.data && (
                      <Grid item xs={12} sm={6}>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          gutterBottom
                        >
                          Railroad Distance
                        </Typography>
                        <Typography variant="body1">
                          {(
                            (enrichment.enrichment_data.railroad_provider.data
                              .railroad_distance_m *
                              3.28084) /
                            5280
                          ).toFixed(2)}{" "}
                          miles
                        </Typography>
                      </Grid>
                    )}
                </Grid>
              </CardContent>
            </Card>
          )}

          {/* Nearby Places */}
          {enrichment.enrichment_data?.places_nearby_provider?.success &&
            enrichment.enrichment_data.places_nearby_provider.data
              ?.places_nearby &&
            enrichment.enrichment_data.places_nearby_provider.data.places_nearby
              .length > 0 && (
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Typography variant="h5" fontWeight="600">
                      Nearby Places
                    </Typography>
                    {enrichment.enrichment_data.places_nearby_provider
                      .cached && (
                      <Chip label="Cached" size="small" color="info" />
                    )}
                  </Box>
                  <Grid container spacing={2} sx={{ mt: 1 }}>
                    {enrichment.enrichment_data.places_nearby_provider.data.places_nearby.map(
                      (place: any, index: number) => (
                        <Grid item xs={12} sm={6} md={4} key={index}>
                          <Card variant="outlined">
                            <CardContent>
                              <Typography
                                variant="subtitle2"
                                fontWeight="600"
                                gutterBottom
                              >
                                {place.name}
                              </Typography>
                              <Chip
                                label={place.type}
                                size="small"
                                sx={{ mb: 1 }}
                              />
                              <Typography
                                variant="body2"
                                color="text.secondary"
                              >
                                {place.distance_miles?.toFixed(2) || "N/A"}{" "}
                                miles away
                              </Typography>
                              {place.rating && (
                                <Box
                                  sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 0.5,
                                    mt: 1,
                                  }}
                                >
                                  <Star
                                    size={14}
                                    fill="#fbbf24"
                                    color="#fbbf24"
                                  />
                                  <Typography variant="body2">
                                    {place.rating}
                                  </Typography>
                                </Box>
                              )}
                            </CardContent>
                          </Card>
                        </Grid>
                      )
                    )}
                  </Grid>
                </CardContent>
              </Card>
            )}

          {/* Custom Locations */}
          {enrichment.enrichment_data?.distance_provider?.success &&
            enrichment.enrichment_data.distance_provider.data?.distances &&
            enrichment.enrichment_data.distance_provider.data.distances.length >
              0 && (
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Typography variant="h5" fontWeight="600">
                      Distances to Your Locations
                    </Typography>
                    {enrichment.enrichment_data.distance_provider.cached && (
                      <Chip label="Cached" size="small" color="info" />
                    )}
                  </Box>
                  <Grid container spacing={2} sx={{ mt: 1 }}>
                    {enrichment.enrichment_data.distance_provider.data.distances.map(
                      (location: any) => (
                        <Grid item xs={12} sm={6} key={location.location_id}>
                          <Card variant="outlined">
                            <CardContent>
                              <Typography
                                variant="subtitle2"
                                fontWeight="600"
                                gutterBottom
                              >
                                {location.location_name}
                              </Typography>
                              <Typography
                                variant="body2"
                                color="text.secondary"
                              >
                                {location.distance_miles?.toFixed(2) || "N/A"}{" "}
                                miles • {location.duration_minutes || "N/A"} min
                                drive
                              </Typography>
                              {location.duration_in_traffic_minutes && (
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                >
                                  ({location.duration_in_traffic_minutes} min
                                  with traffic)
                                </Typography>
                              )}
                            </CardContent>
                          </Card>
                        </Grid>
                      )
                    )}
                  </Grid>
                </CardContent>
              </Card>
            )}

          {/* Enrichment Summary */}
          {enrichment.metadata && (
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" fontWeight="600" gutterBottom>
                  Enrichment Summary
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Providers Run
                    </Typography>
                    <Typography variant="h6">
                      {enrichment.metadata.successful_providers}/
                      {enrichment.metadata.total_providers}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      API Calls
                    </Typography>
                    <Typography variant="h6">
                      {enrichment.metadata.total_api_calls}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Cached Results
                    </Typography>
                    <Typography variant="h6">
                      {enrichment.metadata.cached_providers}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
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
          )}
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
