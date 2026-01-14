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

export interface EnrichmentProviderData {
  data: string | Record<string, string | number | boolean | string[]> | null;
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
  enrichment_data: Record<string, EnrichmentProviderData>;
  metadata: EnrichmentMetadata;
}

// Legacy interfaces for backward compatibility
export interface LegacyEnrichmentData {
  walk_scores: WalkScore;
  nearby_places: NearbyPlace[];
  custom_location_distances: CustomLocationDistance[];
  is_cached: boolean;
  cached_at: string | null;
  enriched_at: string;
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
