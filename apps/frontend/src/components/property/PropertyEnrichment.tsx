/**
 * Property enrichment data display component
 */
import {
  Footprints,
  Bike,
  Bus,
  MapPin,
  Car,
  Clock,
  Star,
  Navigation,
} from "lucide-react";
import { EnrichmentData } from "@/types";
import { Card, CardContent } from "@mui/material";
import { Chip } from "@mui/material";
import { Divider } from "@mui/material";

export interface PropertyEnrichmentProps {
  enrichment: EnrichmentData;
  isLoading?: boolean;
}

const PropertyEnrichment = ({
  enrichment,
  isLoading,
}: PropertyEnrichmentProps) => {
  // Map nested enrichment data to flat structure
  const walkScores = enrichment.enrichment_data.walkscore_provider?.data;
  const isCached = enrichment.enrichment_data.walkscore_provider?.cached;
  const enrichedAt = enrichment.enrichment_data.walkscore_provider?.enriched_at;
  const nearbyPlaces =
    enrichment.enrichment_data.places_nearby_provider?.data?.places_nearby ||
    [];
  const customLocationDistances =
    enrichment.enrichment_data.distance_provider?.data?.distances || [];

  const getScoreColor = (
    score: number | null
  ):
    | "default"
    | "primary"
    | "secondary"
    | "error"
    | "info"
    | "success"
    | "warning" => {
    if (!score) return "default";
    if (score >= 90) return "success";
    if (score >= 70) return "primary";
    if (score >= 50) return "info";
    return "error";
  };

  const getScoreLabel = (score: number | null) => {
    if (!score) return "N/A";
    if (score >= 90) return "Walker's/Biker's Paradise";
    if (score >= 70) return "Very Walkable/Bikeable";
    if (score >= 50) return "Somewhat Walkable/Bikeable";
    if (score >= 25) return "Car-Dependent";
    return "Very Car-Dependent";
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-neutral-200 rounded w-3/4" />
            <div className="h-4 bg-neutral-200 rounded w-1/2" />
            <div className="h-4 bg-neutral-200 rounded w-2/3" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Walk Scores */}
      <Card>
        <CardContent className="pt-6">
          <h2 className="text-xl font-semibold text-neutral-900 mb-6">
            Walkability & Transportation
          </h2>

          <div className="space-y-6">
            {/* Walk Score */}
            {walkScores?.walk_score !== null &&
              walkScores?.walk_score !== undefined && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Footprints className="w-5 h-5 text-neutral-700" />
                      <span className="font-medium text-neutral-900">
                        Walk Score
                      </span>
                    </div>
                    <Chip
                      label={walkScores.walk_score}
                      color={getScoreColor(walkScores.walk_score)}
                      size="small"
                    />
                  </div>
                  <div className="w-full bg-neutral-200 rounded-full h-3 overflow-hidden">
                    <div
                      className="bg-neutral-900 h-full rounded-full transition-all"
                      style={{ width: `${walkScores.walk_score}%` }}
                    />
                  </div>
                  <p className="text-sm text-neutral-600 mt-2">
                    {getScoreLabel(walkScores.walk_score)}
                  </p>
                </div>
              )}

            {/* Bike Score */}
            {walkScores?.bike_score !== null &&
              walkScores?.bike_score !== undefined && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Bike className="w-5 h-5 text-neutral-700" />
                      <span className="font-medium text-neutral-900">
                        Bike Score
                      </span>
                    </div>
                    <Chip
                      label={walkScores.bike_score}
                      color={getScoreColor(walkScores.bike_score)}
                      size="small"
                    />
                  </div>
                  <div className="w-full bg-neutral-200 rounded-full h-3 overflow-hidden">
                    <div
                      className="bg-neutral-900 h-full rounded-full transition-all"
                      style={{ width: `${walkScores.bike_score}%` }}
                    />
                  </div>
                </div>
              )}

            {/* Transit Score */}
            {walkScores?.transit_score !== null &&
              walkScores?.transit_score !== undefined && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Bus className="w-5 h-5 text-neutral-700" />
                      <span className="font-medium text-neutral-900">
                        Transit Score
                      </span>
                    </div>
                    <Chip
                      label={walkScores.transit_score}
                      color={getScoreColor(walkScores.transit_score)}
                      size="small"
                    />
                  </div>
                  <div className="w-full bg-neutral-200 rounded-full h-3 overflow-hidden">
                    <div
                      className="bg-neutral-900 h-full rounded-full transition-all"
                      style={{ width: `${walkScores.transit_score}%` }}
                    />
                  </div>
                </div>
              )}

            {walkScores?.description && (
              <p className="text-sm text-neutral-600 italic">
                {walkScores.description}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Nearby Places */}
      {nearbyPlaces.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h2 className="text-xl font-semibold text-neutral-900 mb-6">
              Nearby Amenities
            </h2>

            <div className="space-y-4">
              {nearbyPlaces.map(
                (place: import("@/types").NearbyPlace, index: number) => (
                  <div key={index}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4 text-neutral-400" />
                          <h3 className="font-medium text-neutral-900">
                            {place.name}
                          </h3>
                        </div>
                        <p className="text-sm text-neutral-500 ml-6">
                          {place.address}
                        </p>
                        <div className="flex items-center gap-4 ml-6 mt-1 text-sm text-neutral-600">
                          <span className="flex items-center gap-1">
                            <Navigation className="w-3 h-3" />
                            {place.distance_miles.toFixed(1)} mi
                          </span>
                          {place.walking_time_minutes && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {place.walking_time_minutes} min walk
                            </span>
                          )}
                          {place.rating !== null &&
                            place.rating !== undefined && (
                              <span className="flex items-center gap-1">
                                <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
                                {place.rating.toFixed(1)}
                              </span>
                            )}
                        </div>
                      </div>
                      <Chip
                        label={place.type.replace(/_/g, " ")}
                        size="small"
                      />
                    </div>
                    {index < nearbyPlaces.length - 1 && (
                      <Divider sx={{ my: 2 }} />
                    )}
                  </div>
                )
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Custom Location Distances */}
      {customLocationDistances.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h2 className="text-xl font-semibold text-neutral-900 mb-6">
              Distances to Your Locations
            </h2>

            <div className="space-y-4">
              {customLocationDistances.map(
                (
                  location: import("@/types").CustomLocationDistance,
                  index: number
                ) => (
                  <div key={location.location_id}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <MapPin className="w-5 h-5 text-neutral-700" />
                          <h3 className="font-medium text-neutral-900">
                            {location.location_name}
                          </h3>
                        </div>
                        <div className="flex items-center gap-4 ml-7 mt-2">
                          <div className="flex items-center gap-1 text-sm text-neutral-600">
                            <Navigation className="w-4 h-4" />
                            <span>
                              {location.distance_miles.toFixed(1)} miles
                            </span>
                          </div>
                          <div className="flex items-center gap-1 text-sm text-neutral-600">
                            <Car className="w-4 h-4" />
                            <span>
                              {location.driving_time_minutes} min drive
                            </span>
                          </div>
                          {location.traffic_time_minutes !== null &&
                            location.traffic_time_minutes !== undefined && (
                              <div className="flex items-center gap-1 text-sm text-neutral-500">
                                <Clock className="w-4 h-4" />
                                <span>
                                  ({location.traffic_time_minutes} min w/
                                  traffic)
                                </span>
                              </div>
                            )}
                        </div>
                      </div>
                    </div>
                    {index < customLocationDistances.length - 1 && (
                      <Divider sx={{ my: 2 }} />
                    )}
                  </div>
                )
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Cache Info */}
      {isCached && (
        <p className="text-xs text-neutral-500 text-center">
          Data cached from{" "}
          {enrichedAt ? new Date(enrichedAt).toLocaleDateString() : ""}
        </p>
      )}
    </div>
  );
};

export { PropertyEnrichment };
