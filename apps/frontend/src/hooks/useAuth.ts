/**
 * Authentication hooks using React Query
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/store/auth';

export const useAuth = () => {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { setAuth, clearAuth, user, isAuthenticated } = useAuthStore();

    // Get current user
    const { data: currentUser, isLoading } = useQuery({
        queryKey: ['currentUser'],
        queryFn: authApi.getCurrentUser,
        enabled: isAuthenticated,
        staleTime: Infinity,
    });

    // Register mutation
    const registerMutation = useMutation({
        mutationFn: authApi.register,
        onSuccess: (data) => {
            setAuth(data.user, data.access_token, data.refresh_token);
            toast.success('Account created successfully!');
            navigate('/', { replace: true });
        },
    });

    // Login mutation
    const loginMutation = useMutation({
        mutationFn: authApi.login,
        onSuccess: (data) => {
            setAuth(data.user, data.access_token, data.refresh_token);
            toast.success('Welcome back!');
            // Navigation is handled by LoginPage to respect the "from" location
        },
    });

    // Logout mutation
    const logoutMutation = useMutation({
        mutationFn: authApi.logout,
        onSuccess: () => {
            clearAuth();
            queryClient.clear();
            toast.success('Logged out successfully');
            navigate('/login', { replace: true });
        },
    });

    return {
        user: currentUser || user,
        isAuthenticated,
        isLoading,
        register: registerMutation.mutate,
        login: loginMutation.mutate,
        logout: logoutMutation.mutate,
        isRegistering: registerMutation.isPending,
        isLoggingIn: loginMutation.isPending,
    };
};
