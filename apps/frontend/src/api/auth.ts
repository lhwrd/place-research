/**
 * Authentication API endpoints
 */
import apiClient from '@/lib/axios';
import { AuthTokens, User } from '@/types';

export interface RegisterData {
    email: string;
    password: string;
    full_name?: string;
}

export interface LoginData {
    username: string; // Email
    password: string;
}

export const authApi = {
    register: async (data: RegisterData): Promise<AuthTokens> => {
        const response = await apiClient.post<AuthTokens>('/auth/register', data);
        return response.data;
    },

    login: async (data: LoginData): Promise<AuthTokens> => {
        const response = await apiClient.post<AuthTokens>(
            '/auth/login',
            new URLSearchParams(
                Object.entries(data).reduce((acc, [key, value]) => {
                    acc[key] = String(value);
                    return acc;
                }, {} as Record<string, string>)
            ),
            {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            }
        );
        return response.data;
    },

    logout: async (): Promise<void> => {
        await apiClient.post('/auth/logout');
    },

    getCurrentUser: async (): Promise<User> => {
        const response = await apiClient.get<User>('/auth/me');
        return response.data;
    },

    refreshToken: async (refreshToken: string): Promise<{ access_token: string }> => {
        const response = await apiClient.post('/auth/refresh', { refresh_token: refreshToken });
        return response.data;
    },
};
