/**
 * Saved properties API endpoints
 */
import apiClient from '@/lib/axios';
import { SavedProperty, PaginatedResponse } from '@/types';

export const savedPropertiesApi = {
    getAll: async (
        skip: number = 0,
        limit: number = 20,
        filters?: {
            is_favorite?: boolean;
            is_archived?: boolean;
            tags?: string;
        }
    ): Promise<PaginatedResponse<SavedProperty>> => {
        const response = await apiClient.get<PaginatedResponse<SavedProperty>>(
            '/saved-properties',
            { params: { skip, limit, ...filters } }
        );
        return response.data;
    },

    getById: async (id: number): Promise<SavedProperty> => {
        const response = await apiClient.get<SavedProperty>(`/saved-properties/${id}`);
        return response.data;
    },

    save: async (data: {
        property_id: number;
        notes?: string;
        rating?: number;
        tags?: string;
        is_favorite?: boolean;
    }): Promise<SavedProperty> => {
        const response = await apiClient.post<SavedProperty>('/saved-properties', data);
        return response.data;
    },

    update: async (id: number, data: Partial<SavedProperty>): Promise<SavedProperty> => {
        const response = await apiClient.put<SavedProperty>(`/saved-properties/${id}`, data);
        return response.data;
    },

    delete: async (id: number): Promise<void> => {
        await apiClient.delete(`/saved-properties/${id}`);
    },

    getStats: async () => {
        const response = await apiClient.get('/saved-properties/stats/summary');
        return response.data;
    },
};
