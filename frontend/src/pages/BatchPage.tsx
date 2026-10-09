import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Suspense, lazy, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { ProgressPanel } from '../components/ProgressPanel'
import { RatingDisplay } from '../components/RatingInput'
import { StatusBadge } from '../components/StatusBadge'
import { useBatch, useChartReadings, useReadings } from '../hooks/useBatches'
import { useTastings } from '../hooks/useTastings'
import { useUnitSystem } from '../hooks/useUnitSystem'
import { STATUSES, STATUS_LABELS, type BatchOut, type BatchStatus, type ReadingOut, nextStatus } from '../lib/batches'
import { describeProblem } from '../lib/problem'
import { formatDate, formatDateTime, fromLocalInputValue, toLocalInputValue } from '../lib/time'
import { type UnitSystem, fToC, formatGravity, formatMeasure, hopWeight, temperature, trim, volume, weight } from '../lib/units'

type BatchUpdate = components['schemas']['BatchUpdate']
type ReadingCreate = components['schemas']['ReadingCreate']

const input = 'mt-1 w-full rounded border border-stone-300 px-2 py-1'

// Chart.js is only needed here, so it loads with this page rather than with the app.
const FermentationChart = lazy(() =>
  import('../components/FermentationChart').then((m) => ({ default: m.FermentationChart })),
)

export function BatchPage() {
  const { id } = useParams<{ id: string }>()
  const batch = useBatch(id)
  const [system] = useUnitSystem()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['batches'] })

  const update = useMutation({
    mutationFn: async (body: BatchUpdate) => {
      const { data, error, response } = await api.PATCH('/api/v1/batches/{batch_id}', { params: { path: { batch_id: id! } }, body })
      if (!data) throw new Error(describeProblem(error, `Update failed (${response.status})`))
      return data
    },
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: async () => {
      const { response } = await api.DELETE('/api/v1/batches/{batch_id}', { params: { path: { batch_id: id! } } })
      if (!response.ok) throw new Error(`Delete failed (${response.status})`)
    },
    onSuccess: async () => {
      await Promise.all([invalidate(), queryClient.invalidateQueries({ queryKey: ['tastings'] })])
      void navigate('/batches')
    },
  })

  if (batch.isPending) return <p className="text-stone-500">Loading…</p>
  if (batch.isError) {
    return (
      <p role="alert" className="text-red-800">
        {(batch.error as Error).message}. <Link to="/batches" className="underline">Back to batches</Link>
      </p>
    )
  }
  const b = batch.data
  const next = nextStatus(b.status)
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">{b.name}</h1>
        <StatusBadge status={b.status} />
        <span className="flex-1" />
        {next && (
          <button type="button" className="rounded bg-amber-600 px-3 py-1 text-sm text-white hover:bg-amber-700 disabled:opacity-50" disabled={update.isPending} onClick={() => update.mutate({ status: next })}>
            Mark as {STATUS_LABELS[next].toLowerCase()}
          </button>
        )}
        <label className="text-sm">
          <span className="sr-only">Status</span>
          <select className="rounded border border-stone-300 px-2 py-1" value={b.status} onChange={(e) => update.mutate({ status: e.target.value as BatchStatus })}>
            {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
          </select>
        </label>
        <Link to={`/tastings/new?batch=${b.id}`} className="rounded border border-stone-300 px-3 py-1 text-sm hover:bg-stone-100">
          Rate this batch
        </Link>
      </header>
      {update.isError && <p role="alert" className="text-sm text-red-800">{(update.error as Error).message}</p>}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-6">
          <ProgressPanel fermentation={b.fermentation} />
          <ChartSection batchId={b.id} count={b.fermentation.readings_count} system={system} />
          <ReadingForm batchId={b.id} system={system} />
          <ReadingsTable batchId={b.id} system={system} />
          <BatchTastings batchId={b.id} />
        </div>
        <aside className="space-y-6">
          <DetailsForm batch={b} system={system} onSave={(body) => update.mutate(body)} saving={update.isPending} />
          <RecipeSnapshot batch={b} system={system} />
          <button
            type="button"
            className="text-sm text-red-800 hover:underline"
            onClick={() => { if (window.confirm('Delete this batch with its readings and tastings? This cannot be undone.')) remove.mutate() }}
          >
            Delete batch
          </button>
        </aside>
      </div>
    </div>
  )
}

function ChartSection({ batchId, count, system }: { batchId: string; count: number; system: UnitSystem }) {
  const chart = useChartReadings(batchId)
  if (count < 2) {
    return <p className="text-sm text-stone-600">Log at least two readings to see the fermentation chart.</p>
  }
  if (chart.isPending) return <p className="text-sm text-stone-500">Loading chart…</p>
  if (chart.isError) return <p role="alert" className="text-sm text-red-800">{(chart.error as Error).message}</p>
  return (
    <section aria-labelledby="chart" className="rounded border border-stone-200 bg-white p-3">
      <h2 id="chart" className="mb-2 font-semibold">Chart</h2>
      <Suspense fallback={<p className="text-sm text-stone-500">Loading chart…</p>}>
        <FermentationChart readings={chart.data} system={system} />
      </Suspense>
    </section>
  )
}

function ReadingForm({ batchId, system }: { batchId: string; system: UnitSystem }) {
  const queryClient = useQueryClient()
  const [takenAt, setTakenAt] = useState(() => toLocalInputValue(new Date()))
  const [gravity, setGravity] = useState('')
  const [temp, setTemp] = useState('')
  const tempUnit = temperature(0, system).unit
  const add = useMutation({
    mutationFn: async () => {
      const body: ReadingCreate = {
        taken_at: fromLocalInputValue(takenAt),
        gravity_sg: gravity === '' ? null : Number(gravity),
        temp_c: temp === '' ? null : system === 'imperial' ? fToC(Number(temp)) : Number(temp),
      }
      const { data, error, response } = await api.POST('/api/v1/batches/{batch_id}/readings', { params: { path: { batch_id: batchId } }, body })
      if (!data) throw new Error(describeProblem(error, `Could not save the reading (${response.status})`))
    },
    onSuccess: async () => {
      setGravity('')
      setTemp('')
      setTakenAt(toLocalInputValue(new Date()))
      await queryClient.invalidateQueries({ queryKey: ['batches'] })
    },
  })
  return (
    <form className="rounded border border-stone-200 bg-white p-3" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
      <h2 className="mb-2 font-semibold">Log a reading</h2>
      <div className="grid gap-3 sm:grid-cols-[1fr_8rem_8rem_auto] sm:items-end">
        <label className="block text-sm">
          Taken at
          <input type="datetime-local" className={input} value={takenAt} onChange={(e) => setTakenAt(e.target.value)} required />
        </label>
        <label className="block text-sm">
          Gravity (SG)
          <input type="number" step="0.001" min="0.980" max="1.200" className={input} value={gravity} onChange={(e) => setGravity(e.target.value)} placeholder="1.040" />
        </label>
        <label className="block text-sm">
          Temperature ({tempUnit})
          <input type="number" step="0.1" className={input} value={temp} onChange={(e) => setTemp(e.target.value)} />
        </label>
        <button type="submit" disabled={add.isPending || (gravity === '' && temp === '')} className="rounded bg-amber-600 px-3 py-1 text-sm text-white disabled:opacity-50">
          Add
        </button>
      </div>
      {add.isError && <p role="alert" className="mt-2 text-sm text-red-800">{(add.error as Error).message}</p>}
    </form>
  )
}

function ReadingsTable({ batchId, system }: { batchId: string; system: UnitSystem }) {
  const readings = useReadings(batchId)
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: async (readingId: string) => {
      const { response } = await api.DELETE('/api/v1/batches/{batch_id}/readings/{reading_id}', { params: { path: { batch_id: batchId, reading_id: readingId } } })
      if (!response.ok) throw new Error(`Delete failed (${response.status})`)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['batches'] }),
  })
  const items: ReadingOut[] = readings.data?.pages.flatMap((p) => p.items) ?? []
  if (readings.isSuccess && items.length === 0) return null
  return (
    <section aria-labelledby="readings" className="space-y-2">
      <h2 id="readings" className="font-semibold">Readings</h2>
      {readings.isError && <p role="alert" className="text-sm text-red-800">{(readings.error as Error).message}</p>}
      <table className="w-full text-sm">
        <thead className="text-left text-stone-500">
          <tr>
            <th className="py-1 pr-3">Taken</th>
            <th className="py-1 pr-3">Gravity</th>
            <th className="py-1 pr-3">Temperature</th>
            <th className="py-1 pr-3">Source</th>
            <th className="py-1"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id} className="border-t border-stone-200">
              <td className="py-1 pr-3">{formatDateTime(r.taken_at)}</td>
              <td className="py-1 pr-3">{r.gravity_sg === null ? '–' : formatGravity(r.gravity_sg)}</td>
              <td className="py-1 pr-3">{r.temp_c === null ? '–' : formatMeasure(temperature(r.temp_c, system), 1)}</td>
              <td className="py-1 pr-3 text-stone-600">{r.source}</td>
              <td className="py-1 text-right">
                <button type="button" className="text-red-800 hover:underline" onClick={() => remove.mutate(r.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {readings.hasNextPage && (
        <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm" onClick={() => readings.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  )
}

function BatchTastings({ batchId }: { batchId: string }) {
  const tastings = useTastings({ batchId })
  const items = tastings.data?.pages.flatMap((p) => p.items) ?? []
  if (items.length === 0) return null
  return (
    <section aria-labelledby="batch-tastings" className="space-y-2">
      <h2 id="batch-tastings" className="font-semibold">Tastings</h2>
      <ul className="divide-y divide-stone-200 text-sm">
        {items.map((t) => (
          <li key={t.id} className="flex items-center justify-between py-2">
            <Link to={`/tastings/${t.id}`} className="text-amber-800 hover:underline">{formatDateTime(t.tasted_at)}</Link>
            <RatingDisplay rating={t.rating} />
          </li>
        ))}
      </ul>
    </section>
  )
}

function DetailsForm({ batch, system, onSave, saving }: { batch: BatchOut; system: UnitSystem; onSave: (body: BatchUpdate) => void; saving: boolean }) {
  const [name, setName] = useState(batch.name)
  const [brewDate, setBrewDate] = useState(batch.brew_date ?? '')
  const [volumeText, setVolumeText] = useState(trim(volume(batch.volume_l, system).value, 2))
  const [og, setOg] = useState(batch.measured_og === null ? '' : batch.measured_og.toFixed(3))
  const [fg, setFg] = useState(batch.measured_fg === null ? '' : batch.measured_fg.toFixed(3))
  const [notes, setNotes] = useState(batch.notes)
  const vol = volume(0, system).unit
  return (
    <form
      className="space-y-3 rounded border border-stone-200 bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault()
        onSave({
          name,
          brew_date: brewDate || null,
          volume_l: volumeText === '' ? undefined : (system === 'imperial' ? Number(volumeText) * 3.785411784 : Number(volumeText)),
          measured_og: og === '' ? null : Number(og),
          measured_fg: fg === '' ? null : Number(fg),
          notes,
        })
      }}
    >
      <h2 className="font-semibold">Details</h2>
      <label className="block text-sm">Name<input className={input} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required /></label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">Brew day<input type="date" className={input} value={brewDate} onChange={(e) => setBrewDate(e.target.value)} /></label>
        <label className="block text-sm">Volume ({vol})<input type="number" step="any" min="0" className={input} value={volumeText} onChange={(e) => setVolumeText(e.target.value)} /></label>
        <label className="block text-sm">Measured OG<input type="number" step="0.001" min="0.980" max="1.200" className={input} value={og} onChange={(e) => setOg(e.target.value)} placeholder={formatGravity(batch.expected.og)} /></label>
        <label className="block text-sm">Measured FG<input type="number" step="0.001" min="0.980" max="1.200" className={input} value={fg} onChange={(e) => setFg(e.target.value)} placeholder={formatGravity(batch.expected.fg)} /></label>
      </div>
      <label className="block text-sm">Notes<textarea className={`${input} min-h-20`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={10_000} /></label>
      <p className="text-xs text-stone-500">Brewed {batch.brew_date ? formatDate(batch.brew_date) : 'on an unknown day'}; created {formatDateTime(batch.created_at)}.</p>
      <button type="submit" disabled={saving} className="rounded border border-stone-300 px-3 py-1 text-sm disabled:opacity-50">Save details</button>
    </form>
  )
}

function RecipeSnapshot({ batch, system }: { batch: BatchOut; system: UnitSystem }) {
  const r = batch.recipe
  const e = batch.expected
  return (
    <section aria-labelledby="snapshot" className="space-y-2 rounded border border-stone-200 bg-white p-3 text-sm">
      <h2 id="snapshot" className="font-semibold">Recipe as brewed</h2>
      <p>
        {batch.recipe_id ? <Link to={`/recipes/${batch.recipe_id}`} className="text-amber-800 hover:underline">{r.name}</Link> : <span>{r.name} <span className="text-stone-500">(recipe since deleted)</span></span>}
        {r.target_style_name && <span className="text-stone-600"> · {r.target_style_name}</span>}
      </p>
      <dl className="grid grid-cols-5 gap-1 text-center">
        <div><dt className="text-xs uppercase text-stone-500">OG</dt><dd className="font-semibold">{formatGravity(e.og)}</dd></div>
        <div><dt className="text-xs uppercase text-stone-500">FG</dt><dd className="font-semibold">{formatGravity(e.fg)}</dd></div>
        <div><dt className="text-xs uppercase text-stone-500">ABV</dt><dd className="font-semibold">{trim(e.abv, 1)}%</dd></div>
        <div><dt className="text-xs uppercase text-stone-500">IBU</dt><dd className="font-semibold">{trim(e.ibu, 0)}</dd></div>
        <div><dt className="text-xs uppercase text-stone-500">SRM</dt><dd className="font-semibold">{trim(e.srm, 1)}</dd></div>
      </dl>
      <p className="text-stone-600">
        {formatMeasure(volume(r.batch_volume_l, system), 1)} batch, {r.boil_time_min} min boil, {r.brewhouse_efficiency_pct}% efficiency.
      </p>
      <ul className="list-disc pl-5">
        {r.fermentables.map((f, i) => <li key={`f${i}`}>{formatMeasure(weight(f.amount_kg, system))} {f.name}</li>)}
        {r.hops.map((h, i) => <li key={`h${i}`}>{formatMeasure(hopWeight(h.amount_g, system), 1)} {h.name}, {h.use === 'dry_hop' ? `dry hop ${h.dry_hop_days} d` : h.use === 'first_wort' ? 'first wort' : `${h.use} ${h.time_min} min`}</li>)}
        {r.yeasts.map((y, i) => <li key={`y${i}`}>{y.name} ({y.attenuation_pct}% attenuation)</li>)}
      </ul>
    </section>
  )
}
