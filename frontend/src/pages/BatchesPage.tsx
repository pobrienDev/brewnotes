import { useState } from 'react'
import { Link } from 'react-router'

import { StatusBadge } from '../components/StatusBadge'
import { useBatches } from '../hooks/useBatches'
import { useUnitSystem } from '../hooks/useUnitSystem'
import { STATUSES, STATUS_LABELS, type BatchStatus, type BatchSummary } from '../lib/batches'
import { formatDate } from '../lib/time'
import { formatGravity, formatMeasure, trim, volume } from '../lib/units'

export function BatchesPage() {
  const [status, setStatus] = useState<BatchStatus | null>(null)
  const [system] = useUnitSystem()
  const batches = useBatches(status)
  const items: BatchSummary[] = batches.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Batches</h1>
        <Link to="/batches/new" className="rounded bg-amber-600 px-3 py-1 text-white hover:bg-amber-700">
          New batch
        </Link>
      </header>
      <div role="tablist" aria-label="Status" className="flex flex-wrap gap-2 border-b border-stone-200">
        {[null, ...STATUSES].map((s) => (
          <button
            key={s ?? 'all'}
            role="tab"
            type="button"
            aria-selected={status === s}
            onClick={() => setStatus(s)}
            className={`px-3 py-2 text-sm ${status === s ? 'border-b-2 border-amber-600 font-medium' : 'text-stone-600'}`}
          >
            {s ? STATUS_LABELS[s] : 'All'}
          </button>
        ))}
      </div>
      {batches.isPending && <p className="text-stone-500">Loading…</p>}
      {batches.isError && <p role="alert" className="text-red-800">{(batches.error as Error).message}</p>}
      {batches.isSuccess && items.length === 0 && (
        <p className="text-stone-600">
          No batches{status ? ` ${STATUS_LABELS[status].toLowerCase()}` : ''} yet.{' '}
          <Link to="/batches/new" className="text-amber-700 hover:underline">Brew one from a saved recipe</Link>.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-stone-500">
              <tr>
                <th className="py-1 pr-3">Batch</th>
                <th className="py-1 pr-3">Status</th>
                <th className="py-1 pr-3">Brew day</th>
                <th className="py-1 pr-3">Volume</th>
                <th className="py-1 pr-3">OG</th>
                <th className="py-1 pr-3">Current</th>
                <th className="py-1 pr-3">ABV</th>
                <th className="py-1">Readings</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.id} className="border-t border-stone-200">
                  <td className="py-2 pr-3">
                    <Link to={`/batches/${b.id}`} className="font-medium text-amber-800 hover:underline">
                      {b.name}
                    </Link>
                    <div className="text-xs text-stone-500">
                      {b.recipe_name}
                      {b.target_style_name ? ` · ${b.target_style_name}` : ''}
                    </div>
                  </td>
                  <td className="py-2 pr-3"><StatusBadge status={b.status} /></td>
                  <td className="py-2 pr-3 text-stone-700">{b.brew_date ? formatDate(b.brew_date) : '–'}</td>
                  <td className="py-2 pr-3">{formatMeasure(volume(b.volume_l, system), 1)}</td>
                  <td className="py-2 pr-3">{formatGravity(b.fermentation.og)}</td>
                  <td className="py-2 pr-3">{b.fermentation.current_sg === null ? '–' : formatGravity(b.fermentation.current_sg)}</td>
                  <td className="py-2 pr-3">{b.fermentation.abv === null ? '–' : `${trim(b.fermentation.abv, 1)}%`}</td>
                  <td className="py-2">{b.fermentation.readings_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {batches.hasNextPage && (
        <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm" onClick={() => batches.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  )
}
