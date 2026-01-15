/**
 * Shared type definitions
 */

// Re-export preferences types
export * from './preferences';

// User types
export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  last_login:  string | null;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

// Property types
export interface Property {
  id: number;
  address: string;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  county: string | null;
  latitude: number;
  longitude: number;
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  lot_size: number | null;
  year_built: number | null;
  property_type: string | null;
  estimated_value: number | null;
  last_sold_price: number | null;
  last_sold_date: string | null;
  tax_assessed_value: number | null;
  annual_tax:  number | null;
  created_at: string;
  updated_at: string;
}

// Enrichment types
export interface WalkScore {
  walk_score: number | null;
  bike_score: number | null;
  transit_score: number | null;
  description: string | null;
}

export interface NearbyPlace {
  name: string;
  type: string;
  address: string;
  distance_miles: number;
  walking_time_minutes: number | null;
  rating: number | null;
}

export interface CustomLocationDistance {
  location_id: number;
  location_name: string;
  distance_miles: number;
  driving_time_minutes: number;
  traffic_time_minutes: number | null;
}


// WalkScore Provider Data
export interface WalkScoreProviderData {
  walk_score: number | null;
  bike_score: number | null;
  transit_score: number | null;
  description: string | null;
}

// Air Quality Provider Data
export interface AirQualityProviderData {
  DateIssue: string;
  DateForecast: string;
  ReportingArea: string;
  StateCode: string;
  Latitude: number;
  Longitude: number;
  ParameterName: string;
  AQI: number;
  Category: {
    Number: number;
    Name: string;
  };
  ActionDay: boolean;
  Discussion: string;
}

// Annual Average Climate Provider Data
export interface AnnualAverageClimateProviderData {
  annual_average_temperature: number;
  annual_average_precipitation: number;
}

// Flood Zone Provider Data
export interface FloodZoneProviderData {
  flood_zone: string;
  flood_risk: string;
}

// Highway Provider Data
export interface HighwayProviderData {
  highway_distance_m: number;
  nearest_highway_type: string;
  road_noise_level_db: number;
  road_noise_category: string;
}

// Railroad Provider Data
export interface RailroadProviderData {
  railroad_distance_m: number;
}

// Places Nearby Provider Data
export interface PlacesNearbyProviderData {
  places_nearby: NearbyPlace[];
}

// Distance Provider Data
export interface DistanceProviderData {
  distances: CustomLocationDistance[];
}

// Generic Enrichment Provider Data (fallback)
export interface GenericProviderData {
  // Define as unknown for maximum type safety
  [key: string]: unknown;
}

// Make EnrichmentProviderData generic
export interface EnrichmentProviderData<T = GenericProviderData> {
  data: T | null;
  success: boolean;
  cached: boolean;
  error: string | null;
  enriched_at: string | null;
}

export interface EnrichmentMetadata {
  total_providers: number;
  successful_providers: number;
  failed_providers: number;
  total_api_calls: number;
  cached_providers: number;
}


export interface EnrichmentData {
  success: boolean;
  enrichment_data: {
    walkscore_provider?: EnrichmentProviderData<WalkScoreProviderData>;
    air_quality_provider?: EnrichmentProviderData<AirQualityProviderData>;
    annual_average_climate_provider?: EnrichmentProviderData<AnnualAverageClimateProviderData>;
    flood_zone_provider?: EnrichmentProviderData<FloodZoneProviderData>;
    highway_provider?: EnrichmentProviderData<HighwayProviderData>;
    railroad_provider?: EnrichmentProviderData<RailroadProviderData>;
    places_nearby_provider?: EnrichmentProviderData<PlacesNearbyProviderData>;
    distance_provider?: EnrichmentProviderData<DistanceProviderData>;
  };
  metadata: EnrichmentMetadata;
}

// Saved Property types
export interface SavedProperty {
  id: number;
  user_id: number;
  property_id: number;
  notes: string | null;
  rating: number | null;
  tags: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  viewed_in_person: boolean;
  viewing_date: string | null;
  saved_at: string;
  updated_at: string;
  property:  Property;
}

// Custom Location types
export type LocationType = 'family' | 'friend' | 'work' | 'other';

export interface CustomLocation {
  id:  number;
  user_id: number;
  name: string;
  description: string | null;
  address: string;
  city: string | null;
  state: string | null;
  zip_code:  string | null;
  latitude: number;
  longitude: number;
  location_type: LocationType;
  priority: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// User Preferences types
export interface UserPreferences {
  id: number;
  user_id: number;
  min_walk_score: number | null;
  min_bike_score: number | null;
  min_transit_score: number | null;
  max_grocery_distance:  number | null;
  max_park_distance: number | null;
  max_school_distance: number | null;
  max_hospital_distance: number | null;
  max_commute_time: number | null;
  workplace_address: string | null;
  workplace_latitude: number | null;
  workplace_longitude: number | null;
  preferred_amenities: string[] | null;
  min_bedrooms: number | null;
  min_bathrooms: number | null;
  min_square_feet:  number | null;
  max_year_built: number | null;
  preferred_property_types: string[] | null;
  min_price: number | null;
  max_price: number | null;
  notify_new_listings: boolean;
  notify_price_changes: boolean;
  created_at: string;
  updated_at: string;
}

// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: {
    message:  string;
    type: string;
    details?: Record<string, string | string[]>;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}
