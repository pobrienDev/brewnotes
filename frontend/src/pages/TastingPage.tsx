import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { BreweryPicker } from '../components/BreweryPicker'
import { RatingInput } from '../components/RatingInput'
import { useAllBatches } from '../hooks/useBatches'
import { useAllBeers } from '../hooks/useBeers'
import { useBrewery } from '../hooks/useBreweries'
import { type TastingOut, useTasting } from '../hooks/useTastings'
import type { BreweryRef } from '../lib/map'
import { describeProblem } from '../lib/problem'
import { type Rating, isRating } from '../lib/rating'
import { fromLocalInputValue, toLocalInputValue } from '../lib/time'

type TastingCreate = components['schemas']['TastingCreate']
type TastingUpdate = components['schemas']['TastingUpdate']

const input = 'mt-1 w-full rounded border border-stone-300 px-2 py-1'
const NOTE_FIELDS = [
  ['aroma', 'Aroma', 'Hops, malt, yeast character, off-aromas'],
  ['appearance', 'Appearance', 'Colour, clarity, head'],
  ['flavor', 'Flavor', 'Balance, finish, off-flavours'],
  ['mouthfeel', 'Mouthfeel', 'Body, carbonation, warmth'],
] as const

/** New tasting (/tastings/new?batch=… or ?beer=…) or edit an existing one (/tastings/:id). */
export function TastingPage() {
  const { id } = useParams<{ id: string }>()
  const existing = useTasting(id)
  if (id) {
    if (existing.isPending) return <p className="text-stone-500">Loading…</p>
    if (existing.isError) {
      return (
        <p role="alert" className="text-red-800">
          {(existing.error as Error).message}. <Link to="/tastings" className="underline">Back to tastings</Link>
        </p>
      )
    }
    return <TastingForm tasting={existing.data} />
  }
  return <TastingForm tasting={null} />
}

function TastingForm({ tasting }: { tasting: TastingOut | null }) {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<'batch' | 'beer'>(params.get('beer') ? 'beer' : 'batch')
  const [batchId, setBatchId] = useState(params.get('batch') ?? '')
  const [beerId, setBeerId] = useState(params.get('beer') ?? '')
  const [rating, setRating] = useState<Rating | null>(tasting && isRating(tasting.rating) ? tasting.rating : null)
  const [notes, setNotes] = useState<Record<(typeof NOTE_FIELDS)[number][0] | 'notes', string>>({
    aroma: tasting?.aroma ?? '',
    appearance: tasting?.appearance ?? '',
    flavor: tasting?.flavor ?? '',
    mouthfeel: tasting?.mouthfeel ?? '',
    notes: tasting?.notes ?? '',
  })
  const [tastedAt, setTastedAt] = useState(toLocalInputValue(tasting ? new Date(tasting.tasted_at) : new Date()))
  // Where it was tasted: the existing tasting's brewery, or the one named in ?brewery=, until
  // the user picks or clears one (undefined = untouched).
  const preset = useBrewery(tasting ? undefined : (params.get('brewery') ?? undefined))
  const [chosenBrewery, setChosenBrewery] = useState<BreweryRef | null | undefined>(undefined)
  const presetRef: BreweryRef | null = preset.data
    ? { id: preset.data.id, name: preset.data.name, city: preset.data.city, state_province: preset.data.state_province, country: preset.data.country }
    : null
  const brewery = chosenBrewery === undefined ? (tasting?.brewery ?? presetRef) : chosenBrewery
  const batches = useAllBatches()
  const beers = useAllBeers()

  const save = useMutation({
    mutationFn: async () => {
      if (rating === null) throw new Error('Choose a rating.')
      const shared = { rating, ...notes, tasted_at: fromLocalInputValue(tastedAt), brewery_id: brewery?.id ?? null }
      if (tasting) {
        const body: TastingUpdate = shared
        const { data, error, response } = await api.PATCH('/api/v1/tastings/{tasting_id}', { params: { path: { tasting_id: tasting.id } }, body })
        if (!data) throw new Error(describeProblem(error, `Save failed (${response.status})`))
        return data
      }
      const body: TastingCreate = {
        ...shared,
        batch_id: kind === 'batch' ? batchId : null,
        beer_id: kind === 'beer' ? beerId : null,
      }
      const { data, error, response } = await api.POST('/api/v1/tastings', { body })
      if (!data) throw new Error(describeProblem(error, `Save failed (${response.status})`))
      return data
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['tastings'] }),
        queryClient.invalidateQueries({ queryKey: ['beers'] }),
      ])
      void navigate('/tastings')
    },
  })
  const remove = useMutation({
    mutationFn: async () => {
      const { response } = await api.DELETE('/api/v1/tastings/{tasting_id}', { params: { path: { tasting_id: tasting!.id } } })
      if (!response.ok) throw new Error(`Delete failed (${response.status})`)
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['tastings'] }),
        queryClient.invalidateQueries({ queryKey: ['beers'] }),
      ])
      void navigate('/tastings')
    },
  })

  const subjectChosen = tasting !== null || (kind === 'batch' ? batchId !== '' : beerId !== '')
  return (
    <section className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold">{tasting ? 'Edit tasting' : 'New tasting'}</h1>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
        {tasting ? (
          <p className="text-sm text-stone-700">
            {tasting.batch ? <>Batch: <strong>{tasting.batch.name}</strong></> : tasting.beer ? <>Beer: <strong>{tasting.beer.name}</strong>{tasting.beer.brewery_name ? ` (${tasting.beer.brewery_name})` : ''}</> : null}
          </p>
        ) : (
          <fieldset className="space-y-2">
            <legend className="text-sm">What are you tasting?</legend>
            <div className="flex gap-4 text-sm">
              {(['batch', 'beer'] as const).map((k) => (
                <label key={k} className="flex items-center gap-1">
                  <input type="radio" name="kind" checked={kind === k} onChange={() => setKind(k)} />
                  {k === 'batch' ? 'One of my batches' : 'A commercial beer'}
                </label>
              ))}
            </div>
            {kind === 'batch' ? (
              <label className="block text-sm">
                Batch
                <select className={input} value={batchId} onChange={(e) => setBatchId(e.target.value)} required>
                  <option value="">Choose a batch…</option>
                  {batches.data?.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.status})</option>)}
                </select>
                {batches.isSuccess && batches.data.length === 0 && <span className="block text-xs text-stone-500">No batches yet. <Link to="/batches/new" className="underline">Brew one</Link>.</span>}
              </label>
            ) : (
              <label className="block text-sm">
                Beer
                <select className={input} value={beerId} onChange={(e) => setBeerId(e.target.value)} required>
                  <option value="">Choose a beer…</option>
                  {beers.data?.map((b) => <option key={b.id} value={b.id}>{b.name}{b.brewery_name ? ` (${b.brewery_name})` : ''}</option>)}
                </select>
                {beers.isSuccess && beers.data.length === 0 && <span className="block text-xs text-stone-500">No beers yet. <Link to="/beers" className="underline">Add one</Link>.</span>}
              </label>
            )}
          </fieldset>
        )}

        <RatingInput value={rating} onChange={setRating} />

        <BreweryPicker value={brewery} onChange={setChosenBrewery} label="Where (optional)" />

        <div className="grid gap-3 sm:grid-cols-2">
          {NOTE_FIELDS.map(([key, label, hint]) => (
            <label key={key} className="block text-sm">
              {label}
              <textarea className={`${input} min-h-16`} value={notes[key]} onChange={(e) => setNotes((n) => ({ ...n, [key]: e.target.value }))} maxLength={2000} placeholder={hint} />
            </label>
          ))}
        </div>
        <label className="block text-sm">
          Overall
          <textarea className={`${input} min-h-20`} value={notes.notes} onChange={(e) => setNotes((n) => ({ ...n, notes: e.target.value }))} maxLength={10_000} placeholder="Would you brew or buy it again?" />
        </label>
        <label className="block text-sm sm:w-64">
          Tasted at
          <input type="datetime-local" className={input} value={tastedAt} onChange={(e) => setTastedAt(e.target.value)} required />
        </label>
        {save.isError && <p role="alert" className="text-sm text-red-800">{(save.error as Error).message}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={save.isPending || rating === null || !subjectChosen} className="rounded bg-amber-600 px-3 py-1 text-white disabled:opacity-50">
            {tasting ? 'Save changes' : 'Save tasting'}
          </button>
          <Link to="/tastings" className="px-3 py-1 text-sm">Cancel</Link>
          {tasting && (
            <button type="button" className="ml-auto text-sm text-red-800 hover:underline" onClick={() => { if (window.confirm('Delete this tasting?')) remove.mutate() }}>
              Delete tasting
            </button>
          )}
        </div>
      </form>
    </section>
  )
}
