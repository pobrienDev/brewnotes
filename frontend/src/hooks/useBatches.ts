import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { BatchOut, BatchStatus, ReadingOut } from '../lib/batches'
import { describeProblem } from '../lib/problem'

export const batchKeys = {
  all: ['batches'] as const,
  list: (status: BatchStatus | null) => ['batches', 'list', status] as const,
  detail: (id: string) => ['batches', 'detail', id] as const,
  readings: (id: string) => ['batches', 'readings', id] as const,
  chart: (id: string) => ['batches', 'chart', id] as const,
}

export function useBatches(status: BatchStatus | null) {
  return useInfiniteQuery({
    queryKey: batchKeys.list(status),
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET('/api/v1/batches', {
        params: { query: { status: status ?? undefined, cursor: pageParam ?? undefined } },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load batches'))
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

/** Every batch, for pickers. Follows the cursors; bounded by the batch quota. */
export function useAllBatches() {
  return useQuery({
    queryKey: ['batches', 'all'],
    queryFn: async () => {
      const items = []
      let cursor: string | null = null
      do {
        const { data, error } = await api.GET('/api/v1/batches', {
          params: { query: { limit: 100, cursor: cursor ?? undefined } },
        })
        if (!data) throw new Error(describeProblem(error, 'Could not load batches'))
        items.push(...data.items)
        cursor = data.next_cursor
      } while (cursor)
      return items
    },
  })
}

export function useBatch(id: string | undefined) {
  return useQuery({
    queryKey: batchKeys.detail(id ?? ''),
    enabled: Boolean(id),
    queryFn: async (): Promise<BatchOut> => {
      const { data, error, response } = await api.GET('/api/v1/batches/{batch_id}', {
        params: { path: { batch_id: id! } },
      })
      if (!data) throw new Error(response.status === 404 ? 'No such batch' : describeProblem(error))
      return data
    },
  })
}

export function useReadings(batchId: string | undefined) {
  return useInfiniteQuery({
    queryKey: batchKeys.readings(batchId ?? ''),
    enabled: Boolean(batchId),
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET('/api/v1/batches/{batch_id}/readings', {
        params: { path: { batch_id: batchId! }, query: { cursor: pageParam ?? undefined } },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load readings'))
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

/** The whole series downsampled by the server, oldest first, for the chart. */
export function useChartReadings(batchId: string | undefined, points = 200) {
  return useQuery({
    queryKey: [...batchKeys.chart(batchId ?? ''), points],
    enabled: Boolean(batchId),
    queryFn: async (): Promise<ReadingOut[]> => {
      const { data, error } = await api.GET('/api/v1/batches/{batch_id}/readings', {
        params: { path: { batch_id: batchId! }, query: { points } },
      })
      if (!data) throw new Error(describeProblem(error, 'Could not load the chart'))
      return data.items
    },
  })
}
