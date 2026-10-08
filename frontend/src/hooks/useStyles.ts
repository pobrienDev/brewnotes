import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'

export type StyleSummary = components['schemas']['StyleSummary']
export type StyleDetail = components['schemas']['StyleDetail']

/** All styles in guideline order (two pages of 100). Cached for the session. */
export function useAllStyles() {
  return useQuery({
    queryKey: ['styles', 'all'],
    queryFn: async (): Promise<StyleSummary[]> => {
      const items: StyleSummary[] = []
      let cursor: string | null = null
      do {
        const { data, error } = await api.GET('/api/v1/styles', {
          params: { query: { limit: 100, cursor: cursor ?? undefined } },
        })
        if (error) throw new Error(error.title)
        items.push(...data.items)
        cursor = data.next_cursor
      } while (cursor)
      return items
    },
    staleTime: Number.POSITIVE_INFINITY,
  })
}

export function useStyle(slug: string | undefined) {
  return useQuery({
    queryKey: ['styles', slug],
    enabled: Boolean(slug),
    queryFn: async (): Promise<StyleDetail> => {
      const { data, error, response } = await api.GET('/api/v1/styles/{slug}', {
        params: { path: { slug: slug! } },
      })
      if (!data) throw new Error(response.status === 404 ? 'No such style' : error?.title ?? 'Failed')
      return data
    },
    staleTime: Number.POSITIVE_INFINITY,
  })
}
