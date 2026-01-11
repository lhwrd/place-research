/**
 * Side-by-side property comparison component
 */
import { Property } from "@/types";
import { Card, CardContent } from "@mui/material";
import { Chip } from "@mui/material";
import {
  Bed,
  Bath,
  Maximize,
  Calendar,
  DollarSign,
  MapPin,
} from "lucide-react";

export interface PropertyComparisonProps {
  properties: Property[];
  maxProperties?: number;
}

const PropertyComparison = ({
  properties,
  maxProperties = 3,
}: PropertyComparisonProps) => {
  const compareProperties = properties.slice(0, maxProperties);

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

  const comparisonRows = [
    {
      label: "Address",
      icon: MapPin,
      getValue: (p: Property) => (
        <div>
          <p className="font-medium">{p.address}</p>
          <p className="text-sm text-neutral-500">
            {p.city}, {p.state}
          </p>
        </div>
      ),
    },
    {
      label: "Price",
      icon: DollarSign,
      getValue: (p: Property) => formatCurrency(p.estimated_value),
    },
    {
      label: "Bedrooms",
      icon: Bed,
      getValue: (p: Property) => p.bedrooms || "N/A",
    },
    {
      label: "Bathrooms",
      icon: Bath,
      getValue: (p: Property) => p.bathrooms || "N/A",
    },
    {
      label: "Square Feet",
      icon: Maximize,
      getValue: (p: Property) => formatNumber(p.square_feet),
    },
    {
      label: "Year Built",
      icon: Calendar,
      getValue: (p: Property) => p.year_built || "N/A",
    },
    {
      label: "Property Type",
      icon: null,
      getValue: (p: Property) => p.property_type || "N/A",
    },
    {
      label: "Annual Tax",
      icon: DollarSign,
      getValue: (p: Property) => formatCurrency(p.annual_tax),
    },
  ];

  return (
    <Card className="overflow-x-auto">
      <CardContent className="p-0">
        <table className="w-full">
          <thead className="bg-neutral-50 border-b border-neutral-200">
            <tr>
              <th className="px-6 py-4 text-left text-sm font-semibold text-neutral-900 w-48">
                Feature
              </th>
              {compareProperties.map((property) => (
                <th
                  key={property.id}
                  className="px-6 py-4 text-left text-sm font-semibold text-neutral-900 min-w-[200px]"
                >
                  <Chip label={`Property ${property.id}`} size="small" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200">
            {comparisonRows.map((row, index) => (
              <tr key={index} className="hover:bg-neutral-50">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-neutral-900">
                    {row.icon && (
                      <row.icon className="w-4 h-4 text-neutral-400" />
                    )}
                    {row.label}
                  </div>
                </td>
                {compareProperties.map((property) => (
                  <td
                    key={property.id}
                    className="px-6 py-4 text-sm text-neutral-900"
                  >
                    {row.getValue(property)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
};

export { PropertyComparison };
