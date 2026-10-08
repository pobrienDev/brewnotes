import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export function useProviders() {
  return useQuery({
    queryKey: ['auth', 'providers'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/v1/auth/providers')
      if (error) throw new Error(error.title)
      return data.providers
    },
    staleTime: Number.POSITIVE_INFINITY,
  })
}
