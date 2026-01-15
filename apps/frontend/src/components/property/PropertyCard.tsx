/**
 * Property card component for displaying property summary
 */
import { Link } from "react-router-dom";
import { MapPin, Bed, Bath, Maximize, Heart } from "lucide-react";
import { Property } from "@/types";
import {
  Card,
  CardContent,
  Box,
  IconButton,
  Grid,
  Typography,
} from "@mui/material";
import { Button } from "@mui/material";

export interface PropertyCardProps {
  property: Property;
  onSave?: (property: Property) => void;
  onRemove?: (property: Property) => void;
  isSaved?: boolean;
  showActions?: boolean;
  variant?: "default" | "compact";
  className?: string;
}

const PropertyCard = ({
  property,
  onSave,
  onRemove,
  isSaved = false,
  showActions = true,
  variant = "default",
  className,
}: PropertyCardProps) => {
  const formatNumber = (value: number | null) => {
    if (!value) return "N/A";
    return new Intl.NumberFormat("en-US").format(value);
  };

  const handleSaveToggle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (isSaved && onRemove) {
      onRemove(property);
    } else if (onSave) {
      onSave(property);
    }
  };

  if (variant === "compact") {
    return (
      <Card
        sx={{
          overflow: "hidden",
          "&:hover": {
            boxShadow: 3,
          },
          transition: "box-shadow 0.2s",
        }}
        className={className}
      >
        <CardContent sx={{ p: 1.5 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Link
              to={`/properties/${property.id}`}
              style={{
                flexGrow: 1,
                minWidth: 0,
                textDecoration: "none",
                color: "inherit",
              }}
            >
              <Box
                sx={{
                  fontSize: "0.875rem",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                <Box
                  component="span"
                  sx={{ fontWeight: 600, color: "neutral.900" }}
                >
                  {property.address}
                </Box>
                <Box component="span" sx={{ color: "neutral.500", ml: 1 }}>
                  {property.city}, {property.state} {property.zip_code}
                </Box>
                {property.bedrooms && (
                  <Box component="span" sx={{ color: "neutral.600", ml: 2 }}>
                    <Bed
                      style={{
                        width: 16,
                        height: 16,
                        display: "inline",
                        marginRight: 4,
                      }}
                    />
                    {property.bedrooms}
                  </Box>
                )}
                {property.bathrooms && (
                  <Box component="span" sx={{ color: "neutral.600", ml: 1.5 }}>
                    <Bath
                      style={{
                        width: 16,
                        height: 16,
                        display: "inline",
                        marginRight: 4,
                      }}
                    />
                    {property.bathrooms}
                  </Box>
                )}
                {property.square_feet && (
                  <Box component="span" sx={{ color: "neutral.600", ml: 1.5 }}>
                    <Maximize
                      style={{
                        width: 16,
                        height: 16,
                        display: "inline",
                        marginRight: 4,
                      }}
                    />
                    {formatNumber(property.square_feet)} sqft
                  </Box>
                )}
              </Box>
            </Link>

            {/* Save button */}
            {showActions && (
              <IconButton
                onClick={handleSaveToggle}
                sx={{
                  p: 0.5,
                  flexShrink: 0,
                  "&:hover": {
                    backgroundColor: "neutral.100",
                  },
                }}
              >
                <Heart
                  style={{
                    width: 20,
                    height: 20,
                    fill: isSaved ? "#ef4444" : "none",
                    color: isSaved ? "#ef4444" : "#a3a3a3",
                  }}
                />
              </IconButton>
            )}
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Link to={`/properties/${property.id}`} style={{ textDecoration: "none" }}>
      <Card
        sx={{
          overflow: "hidden",
          "&:hover": {
            boxShadow: 3,
          },
          transition: "box-shadow 0.2s",
        }}
        className={className}
      >
        {/* Property Image Placeholder */}
        <Box
          sx={{
            position: "relative",
            height: 192,
            background: "linear-gradient(135deg, #f5f5f5 0%, #e5e5e5 100%)",
          }}
        >
          <Box
            sx={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <MapPin style={{ width: 48, height: 48, color: "#a3a3a3" }} />
          </Box>

          {/* Save button */}
          {showActions && (
            <IconButton
              onClick={handleSaveToggle}
              sx={{
                position: "absolute",
                top: 12,
                right: 12,
                p: 1,
                backgroundColor: "white",
                boxShadow: 2,
                "&:hover": {
                  boxShadow: 4,
                  backgroundColor: "white",
                },
              }}
            >
              <Heart
                style={{
                  width: 20,
                  height: 20,
                  fill: isSaved ? "#ef4444" : "none",
                  color: isSaved ? "#ef4444" : "#a3a3a3",
                }}
              />
            </IconButton>
          )}
        </Box>

        {/* Property Details */}
        <CardContent sx={{ p: 2 }}>
          {/* Address */}
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: "neutral.900" }}
            >
              {property.address}
            </Typography>
            <Box
              sx={{
                fontSize: "0.875rem",
                color: "neutral.500",
                display: "flex",
                alignItems: "center",
                gap: 0.5,
              }}
            >
              <MapPin style={{ width: 16, height: 16 }} />
              {property.city}, {property.state} {property.zip_code}
            </Box>
          </Box>

          {/* Property Stats */}
          <Grid
            container
            spacing={1.5}
            sx={{
              py: 1.5,
              borderTop: 1,
              borderColor: "neutral.100",
            }}
          >
            {property.bedrooms && (
              <Grid size={{ xs: 4 }}>
                <Box
                  sx={{
                    textAlign: "center",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 0.5,
                    color: "neutral.600",
                  }}
                >
                  <Bed style={{ width: 16, height: 16 }} />
                  <Typography component="span" sx={{ fontWeight: 600 }}>
                    {property.bedrooms} Beds
                  </Typography>
                </Box>
              </Grid>
            )}
            {property.bathrooms && (
              <Grid size={{ xs: 4 }}>
                <Box
                  sx={{
                    textAlign: "center",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 0.5,
                    color: "neutral.600",
                  }}
                >
                  <Bath style={{ width: 16, height: 16 }} />
                  <Typography component="span" sx={{ fontWeight: 600 }}>
                    {property.bathrooms} Baths
                  </Typography>
                </Box>
              </Grid>
            )}
            {property.square_feet && (
              <Grid size={{ xs: 4 }}>
                <Box
                  sx={{
                    textAlign: "center",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 0.5,
                    color: "neutral.600",
                  }}
                >
                  <Maximize style={{ width: 16, height: 16 }} />
                  <Typography component="span" sx={{ fontWeight: 600 }}>
                    {(property.square_feet / 1000).toFixed(1)}K sqft
                  </Typography>
                </Box>
              </Grid>
            )}
          </Grid>

          {/* Actions */}
          {showActions && (
            <Box sx={{ mt: 2, display: "flex", gap: 1 }}>
              <Button variant="outlined" size="small" fullWidth>
                View Details
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>
    </Link>
  );
};

export { PropertyCard };
