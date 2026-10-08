import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { describeProblem } from '../lib/problem'

export type CalcResult = components['schemas']['CalcResult']
type RecipeInput = components['schemas']['RecipeInput']

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const handle = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(handle)
  }, [value, delayMs])
  return debounced
}

/**
 * Live statistics for the recipe being edited. Changes are debounced by ~300 ms and the query
 * key is the body itself, so an answer to an older body is never shown over a newer one.
 */
export function useRecipeCalc(body: RecipeInput | null) {
  const key = useDebounced(body ? JSON.stringify(body) : null, 300)
  return useQuery({
    queryKey: ['calc', key],
    enabled: key !== null,
    placeholderData: keepPreviousData,
    retry: false,
    queryFn: async (): Promise<CalcResult> => {
      const { data, error, response } = await api.POST('/api/v1/calc', {
        body: JSON.parse(key!) as RecipeInput,
      })
      if (!data) throw new Error(describeProblem(error, `Calculation failed (${response.status})`))
      return data
    },
  })
}
