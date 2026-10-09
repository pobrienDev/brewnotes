import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { BreweryPicker } from '../components/BreweryPicker'
import { RatingDisplay } from '../components/RatingInput'
import { type BeerOut, useBeers } from '../hooks/useBeers'
import { useAllStyles } from '../hooks/useStyles'
import type { BreweryRef } from '../lib/map'
import { describeProblem } from '../lib/problem'
import { trim } from '../lib/units'

type BeerWrite = components['schemas']['BeerWrite']
type BeerUpdate = components['schemas']['BeerUpdate']

const input = 'mt-1 w-full rounded border border-stone-300 px-2 py-1'

export function BeersPage() {
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<BeerOut | null>(null)
  const beers = useBeers(q)
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['beers'] })
  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { response } = await api.DELETE('/api/v1/beers/{beer_id}', { params: { path: { beer_id: id } } })
      if (!response.ok) throw new Error(`Delete failed (${response.status})`)
    },
    onSuccess: async () => { await invalidate(); await queryClient.invalidateQueries({ queryKey: ['tastings'] }) },
  })
  const items = beers.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-bold">Beers</h1>
      <p className="text-sm text-stone-600">Commercial beers you have tried. They are private to your account.</p>
      <div className="grid gap-6 md:grid-cols-[1fr_20rem]">
        <div className="space-y-3">
          <input type="search" className="w-full rounded border border-stone-300 px-2 py-1" placeholder="Search by beer or brewery" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search beers" />
          {beers.isPending && <p className="text-stone-500">Loading…</p>}
          {beers.isError && <p role="alert" className="text-red-800">{(beers.error as Error).message}</p>}
          {beers.isSuccess && items.length === 0 && <p className="text-stone-600">{q ? 'No beers match.' : 'No beers yet. Add one on the right.'}</p>}
          <ul className="divide-y divide-stone-200">
            {items.map((beer) => (
              <li key={beer.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <div>
                  <span className="font-medium">{beer.name}</span>
                  <div className="text-xs text-stone-500">
                    {beer.brewery ? (
                      <Link to={`/breweries/${beer.brewery.id}`} className="text-amber-800 hover:underline">{beer.brewery_name ?? beer.brewery.name}</Link>
                    ) : (
                      beer.brewery_name
                    )}
                    {[beer.style?.display_name, beer.abv === null ? null : `${trim(beer.abv, 1)}% ABV`].filter(Boolean).map((part) => ` · ${part}`).join('')}
                    {!beer.brewery_name && !beer.brewery && !beer.style && beer.abv === null && 'No details'}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {beer.average_rating !== null ? (
                    <span className="text-xs text-stone-600"><RatingDisplay rating={beer.average_rating} /> ({beer.tastings_count})</span>
                  ) : (
                    <span className="text-xs text-stone-500">not rated</span>
                  )}
                  <Link to={`/tastings/new?beer=${beer.id}`} className="text-amber-800 hover:underline">Rate</Link>
                  <button type="button" className="text-amber-800 hover:underline" onClick={() => setEditing(beer)}>Edit</button>
                  <button type="button" className="text-red-800 hover:underline" onClick={() => { if (window.confirm(`Delete ${beer.name} and its tastings?`)) remove.mutate(beer.id) }}>Delete</button>
                </div>
              </li>
            ))}
          </ul>
          {beers.hasNextPage && (
            <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm" onClick={() => beers.fetchNextPage()}>Load more</button>
          )}
        </div>
        <BeerForm key={editing?.id ?? 'new'} beer={editing} onDone={() => { setEditing(null); void invalidate() }} />
      </div>
    </section>
  )
}

function BeerForm({ beer, onDone }: { beer: BeerOut | null; onDone: () => void }) {
  const styles = useAllStyles()
  const [name, setName] = useState(beer?.name ?? '')
  const [brewery, setBrewery] = useState(beer?.brewery_name ?? '')
  const [style, setStyle] = useState(beer?.style?.slug ?? '')
  const [abv, setAbv] = useState(beer?.abv === null || beer?.abv === undefined ? '' : String(beer.abv))
  const [notes, setNotes] = useState(beer?.notes ?? '')
  const [linked, setLinked] = useState<BreweryRef | null>(beer?.brewery ?? null)
  const save = useMutation({
    mutationFn: async () => {
      const body: BeerWrite & BeerUpdate = {
        name,
        brewery_name: brewery.trim() || null,
        style: style || null,
        abv: abv === '' ? null : Number(abv),
        notes,
        brewery_id: linked?.id ?? null,
      }
      const result = beer
        ? await api.PATCH('/api/v1/beers/{beer_id}', { params: { path: { beer_id: beer.id } }, body })
        : await api.POST('/api/v1/beers', { body })
      if (!result.data) throw new Error(describeProblem(result.error, `Save failed (${result.response.status})`))
    },
    onSuccess: () => { setName(''); setBrewery(''); setStyle(''); setAbv(''); setNotes(''); setLinked(null); onDone() },
  })
  return (
    <form className="space-y-3 rounded border border-stone-200 bg-white p-3" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
      <h2 className="font-semibold">{beer ? `Edit ${beer.name}` : 'Add a beer'}</h2>
      <label className="block text-sm">Name<input className={input} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required /></label>
      <label className="block text-sm">Brewery<input className={input} value={brewery} onChange={(e) => setBrewery(e.target.value)} maxLength={200} /></label>
      <BreweryPicker
        value={linked}
        label="On the map (optional)"
        onChange={(b) => {
          setLinked(b)
          if (b && !brewery.trim()) setBrewery(b.name)
        }}
      />
      <label className="block text-sm">
        Style
        <select className={input} value={style} onChange={(e) => setStyle(e.target.value)}>
          <option value="">Unknown</option>
          {styles.data?.map((s) => <option key={s.slug} value={s.slug}>{s.display_name}</option>)}
        </select>
      </label>
      <label className="block text-sm">ABV (%)<input type="number" step="0.1" min="0" max="100" className={input} value={abv} onChange={(e) => setAbv(e.target.value)} /></label>
      <label className="block text-sm">Notes<textarea className={`${input} min-h-16`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={10_000} /></label>
      {save.isError && <p role="alert" className="text-sm text-red-800">{(save.error as Error).message}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending} className="rounded bg-amber-600 px-3 py-1 text-sm text-white disabled:opacity-50">{beer ? 'Save' : 'Add'}</button>
        {beer && <button type="button" className="px-3 py-1 text-sm" onClick={onDone}>Cancel</button>}
      </div>
    </form>
  )
}
