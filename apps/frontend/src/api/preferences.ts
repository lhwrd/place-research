/**
 * User Preferences API endpoints
 */
import apiClient from '@/lib/axios';
import {
  UserPreferences,
  UserPreferencesUpdate,
  AmenityPreferencesUpdate,
  PropertyCriteriaUpdate,
} from '@/types/preferences';

export const preferencesApi = {
  /**
   * Get current user's preferences
   */
  getPreferences: async (): Promise<UserPreferences> => {
    const response = await apiClient.get<UserPreferences>('/preferences');
    return response.data;
  },

  /**
   * Update user preferences (full update)
   */
  updatePreferences: async (data: UserPreferencesUpdate): Promise<UserPreferences> => {
    const response = await apiClient.put<UserPreferences>('/preferences', data);
    return response.data;
  },

  /**
   * Update walkability score preferences
   */
  updateWalkabilityScores: async (data: {
    min_walk_score?: number | null;
    min_bike_score?: number | null;
    min_transit_score?: number | null;
  }): Promise<UserPreferences> => {
    const response = await apiClient.patch<UserPreferences>(
      '/preferences/walkability',
      data
    );
    return response.data;
  },

  /**
   * Update amenity distance preferences
   */
  updateAmenityDistances: async (
    data: AmenityPreferencesUpdate
  ): Promise<UserPreferences> => {
    const response = await apiClient.patch<UserPreferences>(
      '/preferences/amenities',
      data
    );
    return response.data;
  },

  /**
   * Update property criteria
   */
  updatePropertyCriteria: async (
    data: PropertyCriteriaUpdate
  ): Promise<UserPreferences> => {
    const response = await apiClient.patch<UserPreferences>(
      '/preferences/property-criteria',
      data
    );
    return response.data;
  },

  /**
   * Update notification preferences
   */
  updateNotifications: async (data: {
    notify_new_listings?: boolean;
    notify_price_changes?: boolean;
  }): Promise<UserPreferences> => {
    const response = await apiClient.patch<UserPreferences>(
      '/preferences/notifications',
      data
    );
    return response.data;
  },
};
