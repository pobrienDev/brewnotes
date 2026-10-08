import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'

export type CatalogKind = 'fermentables' | 'hops' | 'yeasts'
export type FermentableOut = components['schemas']['FermentableOut']
export type HopOut = components['schemas']['HopOut']
export type YeastOut = components['schemas']['YeastOut']
export type CatalogItem = FermentableOut | HopOut | YeastOut

export function useCatalogSearch(kind: CatalogKind, q: string) {
  return useQuery({
    queryKey: ['catalog', kind, q],
    enabled: q.trim().length >= 2,
    queryFn: async (): Promise<CatalogItem[]> => {
      const { data, error } = await api.GET('/api/v1/catalog/{kind}', {
        params: { path: { kind }, query: { q, limit: 10 } },
      })
      if (error) throw new Error(error.title)
      return data.items as CatalogItem[]
    },
    staleTime: 60_000,
  })
}

/** Every visible item of one kind (built-ins plus the user's own), following the cursors. */
export function useAllCatalog(kind: CatalogKind) {
  return useQuery({
    queryKey: ['catalog', kind, 'all'],
    queryFn: async (): Promise<CatalogItem[]> => {
      const items: CatalogItem[] = []
      let cursor: string | null = null
      do {
        const { data, error } = await api.GET('/api/v1/catalog/{kind}', {
          params: { path: { kind }, query: { limit: 100, cursor: cursor ?? undefined } },
        })
        if (error) throw new Error(error.title)
        items.push(...(data.items as CatalogItem[]))
        cursor = data.next_cursor
      } while (cursor)
      return items
    },
    staleTime: 60_000,
  })
}
