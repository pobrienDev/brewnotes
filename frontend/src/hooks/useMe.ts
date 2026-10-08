import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'

export type Me = components['schemas']['UserOut']

export const ME_KEY = ['me'] as const

/** The signed-in user, or null when anonymous. A 401 is a normal answer, not an error. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      const { data, response } = await api.GET('/api/v1/me')
      if (response.status === 401) return null
      if (!data) throw new Error(`Could not load the account (${response.status})`)
      return data
    },
    staleTime: 60_000,
  })
}

export function useInvalidateMe() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ME_KEY })
}
