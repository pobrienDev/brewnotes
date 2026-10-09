import { Suspense, lazy } from 'react'
import { Link, useParams } from 'react-router'

import { RatingDisplay } from '../components/RatingInput'
import { useBeersAt } from '../hooks/useBeers'
import { useBrewery } from '../hooks/useBreweries'
import { useMe } from '../hooks/useMe'
import { useTastings } from '../hooks/useTastings'
import { formatAddress, typeLabel } from '../lib/map'
import { formatDateTime } from '../lib/time'
import { trim } from '../lib/units'

const BreweryMap = lazy(() => import('../components/BreweryMap').then((m) => ({ default: m.BreweryMap })))

export function BreweryPage() {
  const { id } = useParams<{ id: string }>()
  const brewery = useBrewery(id)
  const me = useMe()
  const tastings = useTastings(me.data ? { breweryId: id } : { breweryId: '__anonymous__' })
  const beers = useBeersAt(me.data ? id : undefined)

  if (brewery.isPending) return <p className="text-stone-500">Loading…</p>
  if (brewery.isError) {
    return (
      <p role="alert" className="text-red-800">
        {(brewery.error as Error).message}. <Link to="/breweries" className="underline">Back to the map</Link>
      </p>
    )
  }
  const b = brewery.data
  const address = formatAddress(b)
  const myTastings = me.data ? (tastings.data?.pages.flatMap((p) => p.items) ?? []) : []
  const myBeers = me.data ? (beers.data ?? []) : []
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">{b.name}</h1>
          <span className="rounded bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-800">{typeLabel(b.brewery_type)}</span>
          {b.removed_at && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-900">No longer listed upstream</span>}
          <span className="flex-1" />
          <Link to={`/tastings/new?brewery=${b.id}`} className="rounded bg-amber-600 px-3 py-1 text-sm text-white hover:bg-amber-700">
            Log a tasting here
          </Link>
        </div>
        <p className="text-sm text-stone-600">
          <Link to="/breweries" className="text-amber-800 hover:underline">Back to the map</Link>
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
        <div className="space-y-6">
          <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-stone-500">Address</dt>
            <dd>{address || 'Not listed'}</dd>
            <dt className="text-stone-500">Website</dt>
            <dd>
              {b.website_url ? (
                <a href={b.website_url} target="_blank" rel="noopener noreferrer" className="text-amber-800 hover:underline">{b.website_url}</a>
              ) : (
                'Not listed'
              )}
            </dd>
            <dt className="text-stone-500">Phone</dt>
            <dd>{b.phone ? <a href={`tel:${b.phone}`} className="text-amber-800 hover:underline">{b.phone}</a> : 'Not listed'}</dd>
          </dl>

          {me.data ? (
            <>
              <section aria-labelledby="my-tastings" className="space-y-2">
                <h2 id="my-tastings" className="font-semibold">Your tastings here</h2>
                {myTastings.length === 0 ? (
                  <p className="text-sm text-stone-600">None yet.</p>
                ) : (
                  <ul className="divide-y divide-stone-200 text-sm">
                    {myTastings.map((t) => (
                      <li key={t.id} className="flex items-center justify-between py-2">
                        <span>
                          <Link to={`/tastings/${t.id}`} className="text-amber-800 hover:underline">
                            {t.beer ? t.beer.name : t.batch ? t.batch.name : 'Tasting'}
                          </Link>
                          <span className="block text-xs text-stone-500">{formatDateTime(t.tasted_at)}</span>
                        </span>
                        <RatingDisplay rating={t.rating} />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section aria-labelledby="my-beers" className="space-y-2">
                <h2 id="my-beers" className="font-semibold">Your beers from here</h2>
                {myBeers.length === 0 ? (
                  <p className="text-sm text-stone-600">
                    None linked yet. Link a beer to this brewery from the <Link to="/beers" className="text-amber-800 hover:underline">beers page</Link>.
                  </p>
                ) : (
                  <ul className="divide-y divide-stone-200 text-sm">
                    {myBeers.map((beer) => (
                      <li key={beer.id} className="flex items-center justify-between py-2">
                        <span>
                          {beer.name}
                          {beer.abv !== null && <span className="text-stone-500"> · {trim(beer.abv, 1)}% ABV</span>}
                        </span>
                        {beer.average_rating !== null && <RatingDisplay rating={beer.average_rating} />}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          ) : (
            <p className="text-sm text-stone-600">
              <Link to={`/sign-in?next=/breweries/${b.id}`} className="text-amber-800 hover:underline">Sign in</Link> to log a tasting here or link your beers to this brewery.
            </p>
          )}
        </div>
        <aside className="space-y-2">
          {b.latitude !== null && b.longitude !== null ? (
            <Suspense fallback={<p className="text-stone-500">Loading map…</p>}>
              <BreweryMap breweries={[b]} initialView={{ center: [b.latitude, b.longitude], zoom: 14 }} className="h-72 w-full" />
            </Suspense>
          ) : (
            <p className="text-sm text-stone-500">No coordinates listed for this brewery.</p>
          )}
          <p className="text-xs text-stone-500">
            Data from Open Brewery DB, last synced {formatDateTime(b.synced_at)}.
          </p>
        </aside>
      </div>
    </div>
  )
}
