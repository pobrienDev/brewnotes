import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { describeProblem } from '../lib/problem'

export type BeerOut = components['schemas']['BeerOut']

export const BEERS_KEY = ['beers'] as const

export function useBeers(q: string) {
  return useInfiniteQuery({
    queryKey: [...BEERS_KEY, 'list', q],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET('/api/v1/beers', {
        params: { query: { q: q || undefined, cursor: pageParam ?? undefined } },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load beers'))
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

/** Every beer, alphabetical, for pickers. */
export function useAllBeers() {
  return useQuery({
    queryKey: [...BEERS_KEY, 'all'],
    queryFn: async (): Promise<BeerOut[]> => {
      const items: BeerOut[] = []
      let cursor: string | null = null
      do {
        const { data, error } = await api.GET('/api/v1/beers', {
          params: { query: { limit: 100, cursor: cursor ?? undefined } },
        })
        if (!data) throw new Error(describeProblem(error, 'Could not load beers'))
        items.push(...data.items)
        cursor = data.next_cursor
      } while (cursor)
      return items
    },
  })
}

/** The user's beers linked to one brewery (for the brewery page). */
export function useBeersAt(breweryId: string | undefined) {
  return useQuery({
    queryKey: [...BEERS_KEY, 'at', breweryId ?? ''],
    enabled: Boolean(breweryId),
    queryFn: async (): Promise<BeerOut[]> => {
      const { data, error } = await api.GET('/api/v1/beers', {
        params: { query: { brewery_id: breweryId!, limit: 100 } },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load beers'))
      return data.items
    },
  })
}
