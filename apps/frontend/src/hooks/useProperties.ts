/**
 * Properties hooks using React Query
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { propertiesApi } from '@/api/properties';

export const usePropertySearch = () => {
  return useMutation({
    mutationFn: propertiesApi.search,
    onSuccess: () => {
      toast.success('Property found!');
    },
  });
};

export const useProperty = (id: number) => {
  return useQuery({
    queryKey: ['property', id],
    queryFn: () => propertiesApi.getById(id),
    enabled: !!id,
  });
};

export const usePropertyEnrichment = (id: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (useCache: boolean = true) => propertiesApi.enrich(id, useCache),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['property', id] });
      toast.success('Property enrichment complete!');
    },
  });
};

export const useUserProperties = (skip: number = 0, limit: number = 20) => {
  return useQuery({
    queryKey: ['userProperties', skip, limit],
    queryFn: () => propertiesApi.getUserProperties(skip, limit),
  });
};
