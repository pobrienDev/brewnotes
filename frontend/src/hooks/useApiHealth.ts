import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export function useApiHealth() {
  return useQuery({
    queryKey: ['health', 'live'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/v1/health/live')
      if (error) throw new Error(error.title)
      return data
    },
  })
}
