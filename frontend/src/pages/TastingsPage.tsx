import { Link } from 'react-router'

import { RatingDisplay } from '../components/RatingInput'
import { StatusBadge } from '../components/StatusBadge'
import { type TastingOut, useTastings } from '../hooks/useTastings'
import { formatDateTime } from '../lib/time'

export function TastingsPage() {
  const tastings = useTastings()
  const items: TastingOut[] = tastings.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Tastings</h1>
        <Link to="/tastings/new" className="rounded bg-amber-600 px-3 py-1 text-white hover:bg-amber-700">New tasting</Link>
      </header>
      {tastings.isPending && <p className="text-stone-500">Loading…</p>}
      {tastings.isError && <p role="alert" className="text-red-800">{(tastings.error as Error).message}</p>}
      {tastings.isSuccess && items.length === 0 && (
        <p className="text-stone-600">
          Nothing tasted yet. Rate one of your <Link to="/batches" className="text-amber-700 hover:underline">batches</Link> or a{' '}
          <Link to="/beers" className="text-amber-700 hover:underline">commercial beer</Link>.
        </p>
      )}
      <ul className="divide-y divide-stone-200">
        {items.map((t) => (
          <li key={t.id} className="py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link to={`/tastings/${t.id}`} className="font-medium text-amber-800 hover:underline">
                {t.batch ? t.batch.name : t.beer ? `${t.beer.name}${t.beer.brewery_name ? ` (${t.beer.brewery_name})` : ''}` : 'Tasting'}
              </Link>
              <RatingDisplay rating={t.rating} />
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
              <span>{t.batch ? 'Homebrew' : 'Commercial'}</span>
              {t.batch && <StatusBadge status={t.batch.status} />}
              <span>{formatDateTime(t.tasted_at)}</span>
            </div>
            {(t.flavor || t.notes) && <p className="mt-1 line-clamp-2 text-sm text-stone-700">{t.flavor || t.notes}</p>}
          </li>
        ))}
      </ul>
      {tastings.hasNextPage && (
        <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm" onClick={() => tastings.fetchNextPage()}>Load more</button>
      )}
    </section>
  )
}
