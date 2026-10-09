import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { describeProblem } from '../lib/problem'

export type RecipeSummary = components['schemas']['RecipeSummary']

/** Every saved recipe, newest first, for the "brew this" picker. */
export function useAllRecipes() {
  return useQuery({
    queryKey: ['recipes', 'all'],
    queryFn: async (): Promise<RecipeSummary[]> => {
      const items: RecipeSummary[] = []
      let cursor: string | null = null
      do {
        const { data, error } = await api.GET('/api/v1/recipes', {
          params: { query: { limit: 100, cursor: cursor ?? undefined } },
        })
        if (!data) throw new Error(describeProblem(error, 'Could not load recipes'))
        items.push(...data.items)
        cursor = data.next_cursor
      } while (cursor)
      return items
    },
  })
}
