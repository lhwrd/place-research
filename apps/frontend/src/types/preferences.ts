/**
 * User Preferences Types
 */

export interface UserPreferences {
  id: number;
  user_id: number;

  // Walkability scores
  min_walk_score?: number | null;
  min_bike_score?: number | null;
  min_transit_score?: number | null;

  // Distance limits (in miles)
  max_grocery_distance?: number | null;
  max_park_distance?: number | null;
  max_school_distance?: number | null;
  max_hospital_distance?: number | null;

  // Commute
  max_commute_time?: number | null;

  // Amenities
  preferred_amenities?: string[] | null;
  preferred_places?: string[] | null;

  // Property criteria
  min_bedrooms?: number | null;
  min_bathrooms?: number | null;
  min_square_feet?: number | null;
  max_year_built?: number | null;
  preferred_property_types?: string[] | null;

  // Budget
  min_price?: number | null;
  max_price?: number | null;

  // Notifications
  notify_new_listings: boolean;
  notify_price_changes: boolean;

  // Metadata
  created_at: string;
  updated_at: string;
}

export interface UserPreferencesUpdate {
  min_walk_score?: number | null;
  min_bike_score?: number | null;
  min_transit_score?: number | null;
  max_grocery_distance?: number | null;
  max_park_distance?: number | null;
  max_school_distance?: number | null;
  max_hospital_distance?: number | null;
  max_commute_time?: number | null;
  preferred_amenities?: string[] | null;
  preferred_places?: string[] | null;
  min_bedrooms?: number | null;
  min_bathrooms?: number | null;
  min_square_feet?: number | null;
  max_year_built?: number | null;
  preferred_property_types?: string[] | null;
  min_price?: number | null;
  max_price?: number | null;
  notify_new_listings?: boolean;
  notify_price_changes?: boolean;
}

export interface AmenityPreferencesUpdate {
  max_grocery_distance?: number | null;
  max_park_distance?: number | null;
  max_school_distance?: number | null;
  max_hospital_distance?: number | null;
}

export interface PropertyCriteriaUpdate {
  min_bedrooms?: number | null;
  min_bathrooms?: number | null;
  min_square_feet?: number | null;
  max_year_built?: number | null;
  preferred_property_types?: string[] | null;
  min_price?: number | null;
  max_price?: number | null;
}
