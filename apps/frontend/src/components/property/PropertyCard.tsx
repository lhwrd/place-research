/**
 * Property card component for displaying property summary
 */
import { Link } from "react-router-dom";
import {
  MapPin,
  Bed,
  Bath,
  Maximize,
  Calendar,
  Heart,
  TrendingUp,
  DollarSign,
} from "lucide-react";
import { Property } from "@/types";
import { Card, CardContent } from "@mui/material";
import { Chip } from "@mui/material";
import { Button } from "@mui/material";
import { cn } from "@/lib/utils";

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
      <Link to={`/properties/${property.id}`}>
        <Card
          className={cn(
            "overflow-hidden hover:shadow-md transition-shadow",
            className
          )}
        >
          <CardContent className="p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold text-neutral-900 line-clamp-1">
                  {property.address}
                </h3>
                <p className="text-sm text-neutral-500">
                  {property.city}, {property.state} {property.zip_code}
                </p>
              </div>
              {showActions && (
                <button
                  onClick={handleSaveToggle}
                  className="p-1 rounded-lg hover:bg-neutral-100 transition-colors"
                >
                  <Heart
                    className={cn(
                      "w-5 h-5",
                      isSaved ? "fill-red-500 text-red-500" : "text-neutral-400"
                    )}
                  />
                </button>
              )}
            </div>

            <div className="flex items-center gap-4 text-sm text-neutral-600">
              {property.bedrooms && (
                <div className="flex items-center gap-1">
                  <Bed className="w-4 h-4" />
                  <span>{property.bedrooms}</span>
                </div>
              )}
              {property.bathrooms && (
                <div className="flex items-center gap-1">
                  <Bath className="w-4 h-4" />
                  <span>{property.bathrooms}</span>
                </div>
              )}
              {property.square_feet && (
                <div className="flex items-center gap-1">
                  <Maximize className="w-4 h-4" />
                  <span>{formatNumber(property.square_feet)} sqft</span>
                </div>
              )}
            </div>

            <div className="mt-3 flex items-center justify-between">
              <span className="text-xl font-bold text-neutral-900">
                {formatCurrency(property.estimated_value)}
              </span>
              {property.property_type && (
                <Chip label={property.property_type} size="small" />
              )}
            </div>
          </CardContent>
        </Card>
      </Link>
    );
  }

  return (
    <Link to={`/properties/${property.id}`}>
      <Card
        className={cn(
          "overflow-hidden hover:shadow-md transition-shadow",
          className
        )}
      >
        {/* Property Image Placeholder */}
        <div className="relative h-48 bg-gradient-to-br from-neutral-100 to-neutral-200">
          <div className="absolute inset-0 flex items-center justify-center">
            <MapPin className="w-12 h-12 text-neutral-400" />
          </div>

          {/* Top badges */}
          <div className="absolute top-3 left-3 flex gap-2">
            {property.property_type && (
              <Chip label={property.property_type} size="small" />
            )}
          </div>

          {/* Save button */}
          {showActions && (
            <button
              onClick={handleSaveToggle}
              className="absolute top-3 right-3 p-2 bg-white rounded-full shadow-md hover:shadow-lg transition-shadow"
            >
              <Heart
                className={cn(
                  "w-5 h-5",
                  isSaved ? "fill-red-500 text-red-500" : "text-neutral-400"
                )}
              />
            </button>
          )}
        </div>

        {/* Property Details */}
        <CardContent className="p-4">
          {/* Price */}
          <div className="mb-3">
            <div className="text-2xl font-bold text-neutral-900">
              {formatCurrency(property.estimated_value)}
            </div>
            {property.last_sold_price && (
              <div className="flex items-center gap-1 text-sm text-neutral-500 mt-1">
                <TrendingUp className="w-4 h-4" />
                <span>
                  Last sold: {formatCurrency(property.last_sold_price)}
                </span>
              </div>
            )}
          </div>

          {/* Address */}
          <div className="mb-3">
            <h3 className="font-semibold text-neutral-900">
              {property.address}
            </h3>
            <p className="text-sm text-neutral-500 flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              {property.city}, {property.state} {property.zip_code}
            </p>
          </div>

          {/* Property Stats */}
          <div className="grid grid-cols-3 gap-3 py-3 border-t border-neutral-100">
            {property.bedrooms && (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 text-neutral-600">
                  <Bed className="w-4 h-4" />
                  <span className="font-semibold">{property.bedrooms}</span>
                </div>
                <p className="text-xs text-neutral-500 mt-1">Beds</p>
              </div>
            )}
            {property.bathrooms && (
              <div className="text-center border-x border-neutral-100">
                <div className="flex items-center justify-center gap-1 text-neutral-600">
                  <Bath className="w-4 h-4" />
                  <span className="font-semibold">{property.bathrooms}</span>
                </div>
                <p className="text-xs text-neutral-500 mt-1">Baths</p>
              </div>
            )}
            {property.square_feet && (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 text-neutral-600">
                  <Maximize className="w-4 h-4" />
                  <span className="font-semibold">
                    {(property.square_feet / 1000).toFixed(1)}K
                  </span>
                </div>
                <p className="text-xs text-neutral-500 mt-1">Sqft</p>
              </div>
            )}
          </div>

          {/* Additional Info */}
          <div className="grid grid-cols-2 gap-2 pt-3 border-t border-neutral-100 text-sm">
            {property.year_built && (
              <div className="flex items-center gap-1 text-neutral-600">
                <Calendar className="w-4 h-4" />
                <span>Built {property.year_built}</span>
              </div>
            )}
            {property.annual_tax && (
              <div className="flex items-center gap-1 text-neutral-600">
                <DollarSign className="w-4 h-4" />
                <span>${(property.annual_tax / 1000).toFixed(1)}K/yr tax</span>
              </div>
            )}
          </div>

          {/* Actions */}
          {showActions && (
            <div className="mt-4 flex gap-2">
              <Button variant="outlined" size="small" fullWidth>
                View Details
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
};

export { PropertyCard };
