import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'
import type { BreweryDetail, BrewerySummary } from '../lib/map'
import { describeProblem } from '../lib/problem'

export type BreweryMapResult = components['schemas']['BreweryMapResult']
export type BreweryTypeCount = components['schemas']['BreweryTypeCount']

export function useBreweriesInBounds(bbox: string | null, types: string[], includeClosed: boolean) {
  return useQuery({
    queryKey: ['breweries', 'map', bbox, [...types].sort(), includeClosed],
    enabled: bbox !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: async (): Promise<BreweryMapResult> => {
      const { data, error } = await api.GET('/api/v1/breweries', {
        params: {
          query: {
            bbox: bbox!,
            type: types.length ? types : undefined,
            include_closed: includeClosed || undefined,
          },
        },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load breweries'))
      return data
    },
  })
}

export function useBrewery(id: string | undefined) {
  return useQuery({
    queryKey: ['breweries', 'detail', id ?? ''],
    enabled: Boolean(id),
    staleTime: 300_000,
    queryFn: async (): Promise<BreweryDetail> => {
      const { data, error, response } = await api.GET('/api/v1/breweries/{brewery_id}', {
        params: { path: { brewery_id: id! } },
      })
      if (!data) throw new Error(response.status === 404 ? 'No such brewery' : describeProblem(error))
      return data
    },
  })
}

export function useBrewerySearch(q: string, limit = 10) {
  const trimmed = q.trim()
  return useQuery({
    queryKey: ['breweries', 'search', trimmed, limit],
    enabled: trimmed.length >= 2,
    staleTime: 60_000,
    queryFn: async (): Promise<BrewerySummary[]> => {
      const { data, error } = await api.GET('/api/v1/breweries/search', {
        params: { query: { q: trimmed, limit } },
      })
      if (!data) throw new Error(describeProblem(error, 'Search failed'))
      return data.items
    },
  })
}

export function useBreweryTypes() {
  return useQuery({
    queryKey: ['breweries', 'types'],
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async (): Promise<BreweryTypeCount[]> => {
      const { data, error } = await api.GET('/api/v1/breweries/types')
      if (!data) throw new Error(describeProblem(error, 'Could not load brewery types'))
      return data
    },
  })
}
