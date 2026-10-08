import { useInfiniteQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { formatGravity, srmColor, trim } from '../lib/units'

type RecipeSummary = components['schemas']['RecipeSummary']

export function RecipesPage() {
  const recipes = useInfiniteQuery({
    queryKey: ['recipes'],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET('/api/v1/recipes', {
        params: { query: { cursor: pageParam ?? undefined } },
      })
      if (error) throw new Error(error.title)
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
  const items: RecipeSummary[] = recipes.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">My recipes</h1>
        <Link to="/recipes/new" className="rounded bg-amber-600 px-3 py-1 text-white hover:bg-amber-700">
          New recipe
        </Link>
      </header>
      {recipes.isPending && <p className="text-stone-500">Loading…</p>}
      {recipes.isError && <p role="alert" className="text-red-800">{(recipes.error as Error).message}</p>}
      {items.length === 0 && recipes.isSuccess && (
        <p className="text-stone-600">
          No recipes yet. <Link to="/recipes/new" className="text-amber-700 hover:underline">Design one</Link>.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-stone-500">
              <tr>
                <th className="py-1 pr-3">Name</th>
                <th className="py-1 pr-3">Target style</th>
                <th className="py-1 pr-3">OG</th>
                <th className="py-1 pr-3">ABV</th>
                <th className="py-1 pr-3">IBU</th>
                <th className="py-1 pr-3">SRM</th>
                <th className="py-1">Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} className="border-t border-stone-200">
                  <td className="py-2 pr-3">
                    <Link to={`/recipes/${r.id}`} className="font-medium text-amber-800 hover:underline">
                      {r.name}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 text-stone-700">{r.target_style?.display_name ?? '–'}</td>
                  <td className="py-2 pr-3">{formatGravity(r.og)}</td>
                  <td className="py-2 pr-3">{trim(r.abv, 1)}%</td>
                  <td className="py-2 pr-3">{trim(r.ibu, 0)}</td>
                  <td className="py-2 pr-3">
                    <span className="inline-flex items-center gap-1">
                      <span aria-hidden="true" className="inline-block h-4 w-4 rounded border border-stone-300" style={{ backgroundColor: srmColor(r.srm) }} />
                      {trim(r.srm, 1)}
                    </span>
                  </td>
                  <td className="py-2 text-stone-600">{new Date(r.updated_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {recipes.hasNextPage && (
        <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm" onClick={() => recipes.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  )
}
