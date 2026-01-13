/**
 * Properties API endpoints
 */
import apiClient from '@/lib/axios';
import { Property, EnrichmentData, PaginatedResponse } from '@/types';

export interface PropertySearchRequest {
  address:  string;
}

export interface PropertySearchResponse {
  success: boolean;
  property: Property;
  message:  string;
}

export interface PropertyEnrichmentResponse {
  success: boolean;
  property_id: number;
  enrichment:  EnrichmentData;
  cached:  boolean;
  message: string;
}

export const propertiesApi = {
  search: async (data: PropertySearchRequest): Promise<PropertySearchResponse> => {
    const response = await apiClient.post<PropertySearchResponse>('/properties/search', data);
    return response.data;
  },

  getById: async (id: number): Promise<PropertySearchResponse> => {
    const response = await apiClient.get<PropertySearchResponse>(`/properties/${id}`);
    return response.data;
  },

  enrich: async (id: number, useCache: boolean = true): Promise<PropertyEnrichmentResponse> => {
    const response = await apiClient. post<PropertyEnrichmentResponse>(
      `/properties/${id}/enrich`,
      null,
      { params: { use_cached: useCache } }
    );
    return response.data;
  },

  getUserProperties: async (skip: number = 0, limit:  number = 20): Promise<PaginatedResponse<Property>> => {
    const response = await apiClient.get<PaginatedResponse<Property>>('/properties', {
      params: { skip, limit },
    });
    return response. data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/properties/${id}`);
  },
};
