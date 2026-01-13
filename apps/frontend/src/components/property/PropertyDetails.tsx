/**
 * Detailed property information component
 */
import {
  MapPin,
  Bed,
  Bath,
  Maximize,
  Calendar,
  Home,
  Ruler,
} from "lucide-react";
import { Property } from "@/types";
import { Card, CardContent } from "@mui/material";
import { Chip } from "@mui/material";
import { Divider } from "@mui/material";

export interface PropertyDetailsProps {
  property: Property;
}

const PropertyDetails = ({ property }: PropertyDetailsProps) => {
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

  const formatDate = (date: string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-neutral-900 mb-2">
                {property.address}
              </h1>
              <p className="text-lg text-neutral-600 flex items-center gap-2">
                <MapPin className="w-5 h-5" />
                {property.city}, {property.state} {property.zip_code}
              </p>
              {property.county && (
                <p className="text-sm text-neutral-500 mt-1">
                  {property.county}
                </p>
              )}
            </div>

            {property.property_type && (
              <Chip label={property.property_type} size="medium" />
            )}
          </div>

          {/* Price Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
            <div>
              <p className="text-sm text-neutral-500 mb-1">Estimated Value</p>
              <p className="text-3xl font-bold text-neutral-900">
                {formatCurrency(property.estimated_value)}
              </p>
            </div>

            {property.last_sold_price && (
              <div>
                <p className="text-sm text-neutral-500 mb-1">Last Sold</p>
                <p className="text-xl font-semibold text-neutral-700">
                  {formatCurrency(property.last_sold_price)}
                </p>
                <p className="text-sm text-neutral-500">
                  {formatDate(property.last_sold_date)}
                </p>
              </div>
            )}

            {property.tax_assessed_value && (
              <div>
                <p className="text-sm text-neutral-500 mb-1">Tax Assessment</p>
                <p className="text-xl font-semibold text-neutral-700">
                  {formatCurrency(property.tax_assessed_value)}
                </p>
                {property.annual_tax && (
                  <p className="text-sm text-neutral-500">
                    {formatCurrency(property.annual_tax)}/year
                  </p>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Property Features */}
      <Card>
        <CardContent className="pt-6">
          <h2 className="text-xl font-semibold text-neutral-900 mb-4">
            Property Features
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {property.bedrooms && (
              <div className="flex items-center gap-3">
                <div className="p-3 bg-neutral-100 rounded-lg">
                  <Bed className="w-6 h-6 text-neutral-700" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-neutral-900">
                    {property.bedrooms}
                  </p>
                  <p className="text-sm text-neutral-500">Bedrooms</p>
                </div>
              </div>
            )}

            {property.bathrooms && (
              <div className="flex items-center gap-3">
                <div className="p-3 bg-neutral-100 rounded-lg">
                  <Bath className="w-6 h-6 text-neutral-700" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-neutral-900">
                    {property.bathrooms}
                  </p>
                  <p className="text-sm text-neutral-500">Bathrooms</p>
                </div>
              </div>
            )}

            {property.square_feet && (
              <div className="flex items-center gap-3">
                <div className="p-3 bg-neutral-100 rounded-lg">
                  <Maximize className="w-6 h-6 text-neutral-700" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-neutral-900">
                    {formatNumber(property.square_feet)}
                  </p>
                  <p className="text-sm text-neutral-500">Square Feet</p>
                </div>
              </div>
            )}

            {property.lot_size && (
              <div className="flex items-center gap-3">
                <div className="p-3 bg-neutral-100 rounded-lg">
                  <Ruler className="w-6 h-6 text-neutral-700" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-neutral-900">
                    {formatNumber(property.lot_size)}
                  </p>
                  <p className="text-sm text-neutral-500">Lot Size (sqft)</p>
                </div>
              </div>
            )}
          </div>

          <Divider sx={{ my: 3 }} />

          {/* Additional Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {property.year_built && (
              <div className="flex items-center gap-2 text-neutral-600">
                <Calendar className="w-5 h-5" />
                <span>Built in {property.year_built}</span>
              </div>
            )}

            {property.property_type && (
              <div className="flex items-center gap-2 text-neutral-600">
                <Home className="w-5 h-5" />
                <span>{property.property_type}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Financial Information */}
      {(property.estimated_value || property.annual_tax) && (
        <Card>
          <CardContent className="pt-6">
            <h2 className="text-xl font-semibold text-neutral-900 mb-4">
              Financial Information
            </h2>

            <div className="space-y-4">
              {property.estimated_value && (
                <div className="flex items-center justify-between">
                  <span className="text-neutral-600">Estimated Value</span>
                  <span className="font-semibold text-neutral-900">
                    {formatCurrency(property.estimated_value)}
                  </span>
                </div>
              )}

              {property.tax_assessed_value && (
                <div className="flex items-center justify-between">
                  <span className="text-neutral-600">Tax Assessed Value</span>
                  <span className="font-semibold text-neutral-900">
                    {formatCurrency(property.tax_assessed_value)}
                  </span>
                </div>
              )}

              {property.annual_tax && (
                <div className="flex items-center justify-between">
                  <span className="text-neutral-600">Annual Property Tax</span>
                  <span className="font-semibold text-neutral-900">
                    {formatCurrency(property.annual_tax)}
                  </span>
                </div>
              )}

              {property.annual_tax && property.estimated_value && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-neutral-500">Effective Tax Rate</span>
                  <span className="text-neutral-700">
                    {(
                      (property.annual_tax / property.estimated_value) *
                      100
                    ).toFixed(2)}
                    %
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Location */}
      <Card>
        <CardContent className="pt-6">
          <h2 className="text-xl font-semibold text-neutral-900 mb-4">
            Location
          </h2>

          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <MapPin className="w-5 h-5 text-neutral-400 mt-0.5" />
              <div>
                <p className="font-medium text-neutral-900">
                  {property.address}
                </p>
                <p className="text-neutral-600">
                  {property.city}, {property.state} {property.zip_code}
                </p>
                {property.county && (
                  <p className="text-sm text-neutral-500">{property.county}</p>
                )}
              </div>
            </div>

            <div className="mt-4 text-sm text-neutral-600">
              <p>
                Coordinates: {property.latitude.toFixed(6)},{" "}
                {property.longitude.toFixed(6)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export { PropertyDetails };
