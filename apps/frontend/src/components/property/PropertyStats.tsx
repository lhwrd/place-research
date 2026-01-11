/**
 * Property statistics summary component
 */
import { TrendingUp, Home, DollarSign, MapPin } from "lucide-react";
import { Card, CardContent } from "@mui/material";

export interface PropertyStatsProps {
  totalProperties: number;
  averagePrice: number;
  savedProperties: number;
  recentlyViewed: number;
}

const PropertyStats = ({
  totalProperties,
  averagePrice,
  savedProperties,
  recentlyViewed,
}: PropertyStatsProps) => {
  const stats = [
    {
      label: "Total Searched",
      value: totalProperties.toLocaleString(),
      icon: MapPin,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      label: "Average Price",
      value: new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(averagePrice),
      icon: DollarSign,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      label: "Saved Properties",
      value: savedProperties.toLocaleString(),
      icon: Home,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
    },
    {
      label: "Recently Viewed",
      value: recentlyViewed.toLocaleString(),
      icon: TrendingUp,
      color: "text-orange-600",
      bgColor: "bg-orange-50",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, index) => (
        <Card key={index} className="hover:shadow-md transition-shadow">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`w-6 h-6 ${stat.color}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-neutral-900">
                  {stat.value}
                </p>
                <p className="text-sm text-neutral-500">{stat.label}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export { PropertyStats };
