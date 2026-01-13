import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Save,
  RotateCcw,
  CheckCircle,
  MapPin,
  Plus,
  Trash2,
  Home,
  Users,
  Briefcase,
  Map,
} from "lucide-react";
import {
  Box,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Stack,
  Card,
  CardContent,
  TextField,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
} from "@mui/material";
import toast from "react-hot-toast";
import { preferencesApi } from "@/api/preferences";
import { UserPreferences, UserPreferencesUpdate } from "@/types/preferences";
import { PREFERENCE_SECTIONS } from "@/config/preferences";
import { PreferenceSectionCard } from "@/components/preferences/PreferenceSectionCard";
import { locationsApi, CustomLocationCreate } from "@/api/locations";
import type { LocationType } from "@/types";

const MAX_CUSTOM_LOCATIONS = 5;

const LOCATION_TYPE_ICONS: Record<LocationType, any> = {
  family: Home,
  friend: Users,
  work: Briefcase,
  other: Map,
};

const LOCATION_TYPE_LABELS: Record<LocationType, string> = {
  family: "Family",
  friend: "Friend",
  work: "Work",
  other: "Other",
};

export const PreferencesPage = () => {
  const queryClient = useQueryClient();
  const [formValues, setFormValues] = useState<Partial<UserPreferences>>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [isAddLocationOpen, setIsAddLocationOpen] = useState(false);
  const [newLocation, setNewLocation] = useState<CustomLocationCreate>({
    name: "",
    address: "",
    location_type: "family",
    priority: 50,
  });

  // Fetch preferences
  const {
    data: preferences,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["preferences"],
    queryFn: preferencesApi.getPreferences,
  });

  // Fetch custom locations
  const { data: locationsData, isLoading: isLoadingLocations } = useQuery({
    queryKey: ["customLocations"],
    queryFn: () => locationsApi.getLocations({ limit: MAX_CUSTOM_LOCATIONS }),
  });

  // Initialize form values when preferences load
  useEffect(() => {
    if (preferences) {
      setFormValues(preferences);
      setHasChanges(false);
    }
  }, [preferences]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: UserPreferencesUpdate) =>
      preferencesApi.updatePreferences(data),
    onSuccess: (data) => {
      queryClient.setQueryData(["preferences"], data);
      setFormValues(data);
      setHasChanges(false);
      toast.success("Preferences saved successfully!");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to save preferences");
    },
  });

  // Create location mutation
  const createLocationMutation = useMutation({
    mutationFn: (data: CustomLocationCreate) =>
      locationsApi.createLocation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customLocations"] });
      setIsAddLocationOpen(false);
      setNewLocation({
        name: "",
        address: "",
        location_type: "family",
        priority: 50,
      });
      toast.success("Location added successfully!");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to add location");
    },
  });

  // Delete location mutation
  const deleteLocationMutation = useMutation({
    mutationFn: (locationId: number) => locationsApi.deleteLocation(locationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customLocations"] });
      toast.success("Location deleted successfully!");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to delete location");
    },
  });

  // Handle field change
  const handleFieldChange = (key: string, value: any) => {
    setFormValues((prev) => ({
      ...prev,
      [key]: value,
    }));
    setHasChanges(true);
  };

  // Handle save
  const handleSave = () => {
    if (!hasChanges) return;

    // Extract only the fields that can be updated
    const updateData: UserPreferencesUpdate = {
      min_walk_score: formValues.min_walk_score,
      min_bike_score: formValues.min_bike_score,
      min_transit_score: formValues.min_transit_score,
      max_grocery_distance: formValues.max_grocery_distance,
      max_park_distance: formValues.max_park_distance,
      max_school_distance: formValues.max_school_distance,
      max_hospital_distance: formValues.max_hospital_distance,
      max_commute_time: formValues.max_commute_time,
      preferred_amenities: formValues.preferred_amenities,
      preferred_places: formValues.preferred_places,
      min_bedrooms: formValues.min_bedrooms,
      min_bathrooms: formValues.min_bathrooms,
      min_square_feet: formValues.min_square_feet,
      max_year_built: formValues.max_year_built,
      preferred_property_types: formValues.preferred_property_types,
      min_price: formValues.min_price,
      max_price: formValues.max_price,
      notify_new_listings: formValues.notify_new_listings,
      notify_price_changes: formValues.notify_price_changes,
    };

    updateMutation.mutate(updateData);
  };

  // Handle reset
  const handleReset = () => {
    if (preferences) {
      setFormValues(preferences);
      setHasChanges(false);
      toast.success("Changes discarded");
    }
  };

  // Handle add location
  const handleAddLocation = () => {
    if (!newLocation.name || !newLocation.address) {
      toast.error("Please provide both name and address");
      return;
    }
    createLocationMutation.mutate(newLocation);
  };

  // Handle delete location
  const handleDeleteLocation = (locationId: number) => {
    if (window.confirm("Are you sure you want to delete this location?")) {
      deleteLocationMutation.mutate(locationId);
    }
  };

  const canAddMoreLocations =
    (locationsData?.total || 0) < MAX_CUSTOM_LOCATIONS;

  // Loading state
  if (isLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "60vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <Box>
          <Typography variant="h3" fontWeight="bold" color="text.primary">
            Preferences
          </Typography>
          <Typography color="text.secondary" mt={1}>
            Customize your property search criteria
          </Typography>
        </Box>
        <Alert severity="error">
          Failed to load preferences. Please try again later.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page Header */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <Box>
          <Typography variant="h3" fontWeight="bold" color="text.primary">
            Preferences
          </Typography>
          <Typography color="text.secondary" mt={1}>
            Customize your property search criteria and notification settings
          </Typography>
        </Box>

        {/* Action Buttons */}
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<RotateCcw size={18} />}
            onClick={handleReset}
            disabled={!hasChanges || updateMutation.isPending}
          >
            Reset
          </Button>
          <Button
            variant="contained"
            startIcon={
              updateMutation.isPending ? (
                <CircularProgress size={18} color="inherit" />
              ) : hasChanges ? (
                <Save size={18} />
              ) : (
                <CheckCircle size={18} />
              )
            }
            onClick={handleSave}
            disabled={!hasChanges || updateMutation.isPending}
          >
            {updateMutation.isPending
              ? "Saving..."
              : hasChanges
              ? "Save Changes"
              : "Saved"}
          </Button>
        </Stack>
      </Box>

      {/* Unsaved Changes Alert */}
      {hasChanges && (
        <Alert severity="info">
          You have unsaved changes. Click "Save Changes" to apply them.
        </Alert>
      )}

      {/* Custom Locations Section */}
      <Card>
        <CardContent>
          <Box sx={{ mb: 3 }}>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mb: 2,
              }}
            >
              <Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <MapPin size={20} />
                  <Typography variant="h6" fontWeight="600">
                    Custom Locations
                  </Typography>
                  <Chip
                    label={`${
                      locationsData?.total || 0
                    }/${MAX_CUSTOM_LOCATIONS}`}
                    size="small"
                    color={canAddMoreLocations ? "default" : "warning"}
                  />
                </Box>
                <Typography variant="body2" color="text.secondary" mt={0.5}>
                  Add important locations to see distances from properties
                </Typography>
              </Box>
              <Button
                variant="contained"
                size="small"
                startIcon={<Plus size={18} />}
                onClick={() => setIsAddLocationOpen(true)}
                disabled={
                  !canAddMoreLocations || createLocationMutation.isPending
                }
              >
                Add Location
              </Button>
            </Box>

            {isLoadingLocations ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
                <CircularProgress size={24} />
              </Box>
            ) : locationsData?.items && locationsData.items.length > 0 ? (
              <Stack spacing={1.5}>
                {locationsData.items.map((location) => {
                  const IconComponent =
                    LOCATION_TYPE_ICONS[location.location_type];
                  return (
                    <Box
                      key={location.id}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        p: 2,
                        border: "1px solid",
                        borderColor: "divider",
                        borderRadius: 1,
                        "&:hover": {
                          bgcolor: "action.hover",
                        },
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 2,
                          flex: 1,
                        }}
                      >
                        <Box
                          sx={{
                            width: 40,
                            height: 40,
                            borderRadius: 1,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            bgcolor: "primary.main",
                            color: "white",
                          }}
                        >
                          {IconComponent && <IconComponent size={20} />}
                        </Box>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography variant="body1" fontWeight="600" noWrap>
                            {location.name}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            noWrap
                          >
                            {location.address}
                          </Typography>
                        </Box>
                        <Chip
                          label={LOCATION_TYPE_LABELS[location.location_type]}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDeleteLocation(location.id)}
                        disabled={deleteLocationMutation.isPending}
                      >
                        <Trash2 size={18} />
                      </IconButton>
                    </Box>
                  );
                })}
              </Stack>
            ) : (
              <Box
                sx={{
                  py: 4,
                  textAlign: "center",
                  border: "1px dashed",
                  borderColor: "divider",
                  borderRadius: 1,
                }}
              >
                <MapPin
                  size={32}
                  style={{ color: "#9e9e9e", marginBottom: 8 }}
                />
                <Typography color="text.secondary">
                  No locations added yet. Add locations to see distances from
                  properties.
                </Typography>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Add Location Dialog */}
      <Dialog
        open={isAddLocationOpen}
        onClose={() => setIsAddLocationOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Custom Location</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name"
              placeholder="e.g., Mom's House, Best Friend's Apt"
              value={newLocation.name}
              onChange={(e) =>
                setNewLocation({ ...newLocation, name: e.target.value })
              }
              fullWidth
              required
            />
            <TextField
              label="Address"
              placeholder="123 Main St, City, State ZIP"
              value={newLocation.address}
              onChange={(e) =>
                setNewLocation({ ...newLocation, address: e.target.value })
              }
              fullWidth
              required
              multiline
              rows={2}
            />
            <FormControl fullWidth>
              <InputLabel>Type</InputLabel>
              <Select
                value={newLocation.location_type}
                onChange={(e) =>
                  setNewLocation({
                    ...newLocation,
                    location_type: e.target.value as LocationType,
                  })
                }
                label="Type"
              >
                <MenuItem value="family">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Home size={18} />
                    Family
                  </Box>
                </MenuItem>
                <MenuItem value="friend">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Users size={18} />
                    Friend
                  </Box>
                </MenuItem>
                <MenuItem value="work">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Briefcase size={18} />
                    Work
                  </Box>
                </MenuItem>
                <MenuItem value="other">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Map size={18} />
                    Other
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Description (Optional)"
              placeholder="Additional details..."
              value={newLocation.description || ""}
              onChange={(e) =>
                setNewLocation({ ...newLocation, description: e.target.value })
              }
              fullWidth
              multiline
              rows={2}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsAddLocationOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleAddLocation}
            disabled={
              createLocationMutation.isPending ||
              !newLocation.name ||
              !newLocation.address
            }
          >
            {createLocationMutation.isPending ? "Adding..." : "Add Location"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Preference Sections */}
      <Stack spacing={3}>
        {PREFERENCE_SECTIONS.map((section) => (
          <PreferenceSectionCard
            key={section.id}
            section={section}
            values={formValues}
            onChange={handleFieldChange}
            disabled={updateMutation.isPending}
          />
        ))}
      </Stack>
    </Box>
  );
};
