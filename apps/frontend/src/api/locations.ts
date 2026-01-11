/**
 * Custom Locations API endpoints
 */
import apiClient from '@/lib/axios';
import { CustomLocation, LocationType } from '@/types';

export interface CustomLocationCreate {
  name: string;
  description?: string | null;
  address?: string;
  latitude?: number;
  longitude?: number;
  location_type?: LocationType;
  priority?: number;
}

export interface CustomLocationUpdate {
  name?: string;
  description?: string | null;
  address?: string;
  latitude?: number;
  longitude?: number;
  location_type?: LocationType;
  priority?: number;
  is_active?: boolean;
}

export interface CustomLocationList {
  items: CustomLocation[];
  total: number;
  skip: number;
  limit: number;
}

export const locationsApi = {
  /**
   * Get all custom locations for the current user
   */
  getLocations: async (params?: {
    skip?: number;
    limit?: number;
    is_active?: boolean;
    location_type?: LocationType;
    sort_by?: string;
    sort_order?: string;
  }): Promise<CustomLocationList> => {
    const response = await apiClient.get<CustomLocationList>('/locations', {
      params,
    });
    return response.data;
  },

  /**
   * Get a specific custom location by ID
   */
  getLocation: async (locationId: number): Promise<CustomLocation> => {
    const response = await apiClient.get<CustomLocation>(`/locations/${locationId}`);
    return response.data;
  },

  /**
   * Create a new custom location
   */
  createLocation: async (data: CustomLocationCreate): Promise<CustomLocation> => {
    const response = await apiClient.post<CustomLocation>('/locations', data);
    return response.data;
  },

  /**
   * Update a custom location
   */
  updateLocation: async (
    locationId: number,
    data: CustomLocationUpdate
  ): Promise<CustomLocation> => {
    const response = await apiClient.put<CustomLocation>(
      `/locations/${locationId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete a custom location
   */
  deleteLocation: async (locationId: number): Promise<void> => {
    await apiClient.delete(`/locations/${locationId}`);
  },

  /**
   * Toggle location active status
   */
  toggleActive: async (locationId: number, isActive: boolean): Promise<CustomLocation> => {
    const response = await apiClient.patch<CustomLocation>(
      `/locations/${locationId}/activate?is_active=${isActive}`
    );
    return response.data;
  },

  /**
   * Update location priority
   */
  updatePriority: async (locationId: number, priority: number): Promise<CustomLocation> => {
    const response = await apiClient.patch<CustomLocation>(
      `/locations/${locationId}/priority?priority=${priority}`
    );
    return response.data;
  },
};
