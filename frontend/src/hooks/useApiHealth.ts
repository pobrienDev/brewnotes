import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export function useApiHealth() {
  return useQuery({
    queryKey: ['health', 'live'],
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/v1/health/live')
      if (!data) throw new Error(error?.title ?? `API unreachable (${response.status})`)
      return data
    },
  })
}
