import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import { describeProblem } from '../lib/problem'
import type { Answers, StyleRecommendations } from '../lib/recommendations'

export const RECOMMENDATIONS_KEY = ['recommendations'] as const

/** Style suggestions from the user's own tastings, blended with any cold-start answers. */
export function useStyleRecommendations(answers: Answers, limit = 10) {
  return useQuery({
    queryKey: [...RECOMMENDATIONS_KEY, 'styles', answers.strength ?? null, answers.bitterness ?? null, answers.color ?? null, limit],
    queryFn: async (): Promise<StyleRecommendations> => {
      const { data, error } = await api.GET('/api/v1/recommendations/styles', {
        params: { query: { strength: answers.strength, bitterness: answers.bitterness, color: answers.color, limit } },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load suggestions'))
      return data
    },
    // Changing an answer refetches; the page keeps showing the last answer meanwhile, so the
    // questions never unmount under the user's pointer.
    placeholderData: keepPreviousData,
  })
}
