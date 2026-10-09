import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { describeProblem } from '../lib/problem'

export type TastingOut = components['schemas']['TastingOut']

export const TASTINGS_KEY = ['tastings'] as const

export interface TastingFilter {
  batchId?: string
  beerId?: string
}

export function useTastings(filter: TastingFilter = {}) {
  return useInfiniteQuery({
    queryKey: [...TASTINGS_KEY, 'list', filter.batchId ?? null, filter.beerId ?? null],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET('/api/v1/tastings', {
        params: {
          query: { batch_id: filter.batchId, beer_id: filter.beerId, cursor: pageParam ?? undefined },
        },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load tastings'))
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useTasting(id: string | undefined) {
  return useQuery({
    queryKey: [...TASTINGS_KEY, 'detail', id ?? ''],
    enabled: Boolean(id),
    queryFn: async (): Promise<TastingOut> => {
      const { data, error, response } = await api.GET('/api/v1/tastings/{tasting_id}', {
        params: { path: { tasting_id: id! } },
      })
      if (!data) throw new Error(response.status === 404 ? 'No such tasting' : describeProblem(error))
      return data
    },
  })
}
