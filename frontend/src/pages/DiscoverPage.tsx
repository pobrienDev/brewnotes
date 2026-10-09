import { Suspense, lazy, useCallback, useRef, useState } from 'react'
import { Link } from 'react-router'

import { useBreweriesInBounds, useBrewerySearch, useBreweryTypes } from '../hooks/useBreweries'
import { useUnitSystem } from '../hooks/useUnitSystem'
import {
  type Bounds,
  type BrewerySummary,
  type LatLng,
  type MapView,
  bboxString,
  distanceKm,
  formatDistance,
  formatPlace,
  readStoredView,
  storeView,
  typeLabel,
} from '../lib/map'

// Leaflet and the cluster plugin only load with the map pages.
const BreweryMap = lazy(() => import('../components/BreweryMap').then((m) => ({ default: m.BreweryMap })))

const LIST_LIMIT = 100

export function DiscoverPage() {
  const [initialView] = useState<MapView>(readStoredView)
  const [bbox, setBbox] = useState<string | null>(null)
  const [types, setTypes] = useState<string[]>([])
  const [includeClosed, setIncludeClosed] = useState(false)
  const [search, setSearch] = useState('')
  const [here, setHere] = useState<LatLng | null>(null)
  const [flyTo, setFlyTo] = useState<{ lat: number; lng: number; zoom: number } | null>(null)
  const [geoError, setGeoError] = useState<string | null>(null)
  const [system] = useUnitSystem()
  const debounce = useRef<number | undefined>(undefined)

  const breweries = useBreweriesInBounds(bbox, types, includeClosed)
  const typeCounts = useBreweryTypes()
  const results = useBrewerySearch(search)

  const onViewChange = useCallback((bounds: Bounds, view: MapView) => {
    storeView(view)
    window.clearTimeout(debounce.current)
    debounce.current = window.setTimeout(() => setBbox(bboxString(bounds)), 250)
  }, [])

  const nearMe = () => {
    if (!('geolocation' in navigator)) {
      setGeoError('This browser has no location support.')
      return
    }
    setGeoError(null)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const point = { lat: position.coords.latitude, lng: position.coords.longitude }
        setHere(point)
        setFlyTo({ ...point, zoom: 11 })
      },
      () => setGeoError('Location was not shared, so the map stays where it is.'),
      { timeout: 10_000, maximumAge: 60_000 },
    )
  }

  const toggleType = (type: string) =>
    setTypes((current) => (current.includes(type) ? current.filter((t) => t !== type) : [...current, type]))

  const items: BrewerySummary[] = breweries.data?.items ?? []
  const withDistance = items.map((b) => ({
    brewery: b,
    km: here && b.latitude !== null && b.longitude !== null ? distanceKm(here, { lat: b.latitude, lng: b.longitude }) : null,
  }))
  withDistance.sort((a, b) => (a.km !== null && b.km !== null ? a.km - b.km : a.brewery.name.localeCompare(b.brewery.name)))
  const listed = withDistance.slice(0, LIST_LIMIT)
  const truncated = breweries.data?.truncated ?? false

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">Discover</h1>
        <p className="text-sm text-stone-600">
          Breweries from{' '}
          <a href="https://www.openbrewerydb.org/" target="_blank" rel="noopener noreferrer" className="text-amber-800 hover:underline">
            Open Brewery DB
          </a>
          . Move the map to explore; sign in to log a tasting at a brewery.
        </p>
      </header>
      <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
        <aside className="space-y-4">
          <div className="space-y-2">
            <input
              type="search"
              aria-label="Search breweries"
              className="w-full rounded border border-stone-300 px-2 py-1"
              placeholder="Search by name or city"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {results.isSuccess && results.data.length === 0 && <p className="text-sm text-stone-500">No breweries match.</p>}
            {results.data && results.data.length > 0 && (
              <ul className="divide-y divide-stone-200 rounded border border-stone-200 bg-white text-sm">
                {results.data.map((b) => (
                  <li key={b.id} className="flex items-center justify-between gap-2 px-2 py-1">
                    <span>
                      <Link to={`/breweries/${b.id}`} className="font-medium text-amber-800 hover:underline">{b.name}</Link>
                      <span className="block text-xs text-stone-500">{typeLabel(b.brewery_type)} · {formatPlace(b)}</span>
                    </span>
                    {b.latitude !== null && b.longitude !== null && (
                      <button type="button" className="text-xs text-amber-800 hover:underline" onClick={() => setFlyTo({ lat: b.latitude!, lng: b.longitude!, zoom: 13 })}>
                        Show
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm hover:bg-stone-100" onClick={nearMe}>
              Near me
            </button>
            {geoError && <span role="status" className="text-xs text-stone-600">{geoError}</span>}
          </div>

          <fieldset className="space-y-1 text-sm">
            <legend className="font-semibold">Type</legend>
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {typeCounts.data?.filter((t) => t.brewery_type !== 'closed').map((t) => (
                <label key={t.brewery_type} className="flex items-center gap-1">
                  <input type="checkbox" checked={types.includes(t.brewery_type)} onChange={() => toggleType(t.brewery_type)} />
                  {typeLabel(t.brewery_type)} <span className="text-xs text-stone-500">({t.count})</span>
                </label>
              ))}
            </div>
            <label className="flex items-center gap-1 pt-1">
              <input type="checkbox" checked={includeClosed} onChange={(e) => setIncludeClosed(e.target.checked)} />
              Include closed breweries
            </label>
            {types.length > 0 && (
              <button type="button" className="text-xs text-amber-800 hover:underline" onClick={() => setTypes([])}>
                Clear type filter
              </button>
            )}
          </fieldset>

          <section aria-labelledby="in-view" className="space-y-1">
            <h2 id="in-view" className="font-semibold">
              In view <span className="text-sm font-normal text-stone-500">({items.length}{truncated ? '+' : ''})</span>
            </h2>
            {breweries.isError && <p role="alert" className="text-sm text-red-800">{(breweries.error as Error).message}</p>}
            {truncated && (
              <p role="status" className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                Showing the first {breweries.data?.limit} in this area. Zoom in to see all of them.
              </p>
            )}
            {breweries.isSuccess && items.length === 0 && <p className="text-sm text-stone-500">No breweries in this area.</p>}
            <ul className="max-h-[50vh] divide-y divide-stone-200 overflow-auto text-sm">
              {listed.map(({ brewery: b, km }) => (
                <li key={b.id} className="py-1">
                  <Link to={`/breweries/${b.id}`} className="font-medium text-amber-800 hover:underline">{b.name}</Link>
                  <span className="block text-xs text-stone-500">
                    {typeLabel(b.brewery_type)} · {formatPlace(b)}
                    {km !== null && ` · ${formatDistance(km, system)}`}
                  </span>
                </li>
              ))}
            </ul>
            {items.length > LIST_LIMIT && <p className="text-xs text-stone-500">The map shows all {items.length}; the list stops at {LIST_LIMIT}.</p>}
          </section>
        </aside>
        <Suspense fallback={<p className="text-stone-500">Loading map…</p>}>
          <BreweryMap breweries={items} initialView={initialView} flyTo={flyTo} onViewChange={onViewChange} />
        </Suspense>
      </div>
    </section>
  )
}
