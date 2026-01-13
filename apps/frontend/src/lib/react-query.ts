/**
 * React Query configuration
 */
import { QueryClient, DefaultOptions } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { AxiosError } from 'axios';

const queryConfig: DefaultOptions = {
    queries: {
        staleTime: 1000 * 60 * 5, // 5 minutes
        gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
        retry: (failureCount, error) => {
            // Don't retry on 4xx errors
            if (error instanceof AxiosError && error.response?.status && error.response.status < 500) {
                return false;
            }
            return failureCount < 2;
        },
        refetchOnWindowFocus: false,
    },
    mutations: {
        onError: (error) => {
            if (error instanceof AxiosError) {
                const message = error.response?.data?.error?.message || error.message;
                toast.error(message);
            } else {
                toast.error('An unexpected error occurred');
            }
        },
    },
};

export const queryClient = new QueryClient({ defaultOptions: queryConfig });
