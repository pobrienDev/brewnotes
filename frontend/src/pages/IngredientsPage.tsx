import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import { type CatalogItem, type CatalogKind, useAllCatalog } from '../hooks/useCatalog'
import { describeProblem } from '../lib/problem'

const input = 'rounded border border-stone-300 px-2 py-1'
const KINDS: { kind: CatalogKind; label: string }[] = [
  { kind: 'fermentables', label: 'Fermentables' },
  { kind: 'hops', label: 'Hops' },
  { kind: 'yeasts', label: 'Yeasts' },
]

export function IngredientsPage() {
  const [kind, setKind] = useState<CatalogKind>('fermentables')
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-bold">My ingredients</h1>
      <p className="text-sm text-stone-600">Your own entries appear in the recipe editor alongside the built-in catalog. Recipes copy the values they use, so editing an entry later never changes a saved recipe.</p>
      <div role="tablist" aria-label="Ingredient type" className="flex gap-2 border-b border-stone-200">
        {KINDS.map((k) => (
          <button key={k.kind} role="tab" type="button" aria-selected={kind === k.kind} onClick={() => setKind(k.kind)} className={`px-3 py-2 text-sm ${kind === k.kind ? 'border-b-2 border-amber-600 font-medium' : 'text-stone-600'}`}>
            {k.label}
          </button>
        ))}
      </div>
      <CustomList key={kind} kind={kind} />
    </section>
  )
}

function CustomList({ kind }: { kind: CatalogKind }) {
  const all = useAllCatalog(kind)
  const queryClient = useQueryClient()
  const mine = (all.data ?? []).filter((i) => i.custom)
  const [editing, setEditing] = useState<CatalogItem | null>(null)
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['catalog', kind] })

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const path = `/api/v1/catalog/${kind}/{item_id}` as '/api/v1/catalog/hops/{item_id}'
      const { response } = await api.DELETE(path, { params: { path: { item_id: id } } })
      if (!response.ok) throw new Error(`Delete failed (${response.status})`)
    },
    onSuccess: invalidate,
  })

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_20rem]">
      <div>
        {all.isPending && <p className="text-stone-500">Loading…</p>}
        {all.isSuccess && mine.length === 0 && <p className="text-stone-600">No custom {kind} yet.</p>}
        <ul className="divide-y divide-stone-200">
          {mine.map((item) => (
            <li key={item.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                <span className="font-medium">{item.name}</span> <span className="text-stone-500">{summary(item)}</span>
              </span>
              <span className="flex gap-2">
                <button type="button" className="text-amber-800 hover:underline" onClick={() => setEditing(item)}>Edit</button>
                <button type="button" className="text-red-800 hover:underline" onClick={() => { if (window.confirm(`Delete ${item.name}?`)) remove.mutate(item.id) }}>Delete</button>
              </span>
            </li>
          ))}
        </ul>
      </div>
      <ItemForm key={editing?.id ?? 'new'} kind={kind} item={editing} onDone={() => { setEditing(null); void invalidate() }} />
    </div>
  )
}

function summary(item: CatalogItem): string {
  if ('ppg' in item) return `${item.type} · ${item.ppg} PPG · ${item.color_lovibond} °L · ${item.default_addition}`
  if ('alpha_typical_pct' in item) return `${item.alpha_typical_pct}% AA${item.origin ? ` · ${item.origin}` : ''}`
  return `${item.lab}${item.product_code ? ` ${item.product_code}` : ''} · ${item.attenuation_min_pct}–${item.attenuation_max_pct}%`
}

type Draft = Record<string, string>

function initialDraft(kind: CatalogKind, item: CatalogItem | null): Draft {
  if (!item) {
    if (kind === 'fermentables') return { name: '', type: 'grain', ppg: '', color_lovibond: '', default_addition: 'mash' }
    if (kind === 'hops') return { name: '', alpha_typical_pct: '', origin: '' }
    return { name: '', lab: '', product_code: '', attenuation_min_pct: '', attenuation_max_pct: '' }
  }
  if ('ppg' in item) return { name: item.name, type: item.type, ppg: String(item.ppg), color_lovibond: String(item.color_lovibond), default_addition: item.default_addition }
  if ('alpha_typical_pct' in item) return { name: item.name, alpha_typical_pct: String(item.alpha_typical_pct), origin: item.origin ?? '' }
  return { name: item.name, lab: item.lab, product_code: item.product_code ?? '', attenuation_min_pct: String(item.attenuation_min_pct), attenuation_max_pct: String(item.attenuation_max_pct) }
}

function toBody(kind: CatalogKind, d: Draft): Record<string, unknown> {
  if (kind === 'fermentables') return { name: d.name, type: d.type, ppg: Number(d.ppg), color_lovibond: Number(d.color_lovibond), default_addition: d.default_addition }
  if (kind === 'hops') return { name: d.name, alpha_typical_pct: Number(d.alpha_typical_pct), origin: d.origin || null }
  return { name: d.name, lab: d.lab, product_code: d.product_code || null, attenuation_min_pct: Number(d.attenuation_min_pct), attenuation_max_pct: Number(d.attenuation_max_pct) }
}

function ItemForm({ kind, item, onDone }: { kind: CatalogKind; item: CatalogItem | null; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>(() => initialDraft(kind, item))
  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setDraft((d) => ({ ...d, [key]: e.target.value }))
  const save = useMutation({
    mutationFn: async () => {
      const body = toBody(kind, draft)
      const base = `/api/v1/catalog/${kind}` as '/api/v1/catalog/hops'
      const result = item
        ? await api.PATCH(`${base}/{item_id}` as '/api/v1/catalog/hops/{item_id}', { params: { path: { item_id: item.id } }, body: body as never })
        : await api.POST(base, { body: body as never })
      if (!result.data) throw new Error(describeProblem(result.error, `Save failed (${result.response.status})`))
    },
    onSuccess: () => { setDraft(initialDraft(kind, null)); onDone() },
  })
  const field = (key: string, label: string, type: 'text' | 'number' = 'text') => (
    <label className="block text-sm">
      {label}
      <input className={`${input} mt-1 w-full`} type={type} step="any" value={draft[key] ?? ''} onChange={set(key)} required={!['origin', 'product_code'].includes(key)} />
    </label>
  )
  return (
    <form className="space-y-3 rounded border border-stone-200 bg-white p-3" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
      <h2 className="font-semibold">{item ? `Edit ${item.name}` : `New ${kind.slice(0, -1)}`}</h2>
      {field('name', 'Name')}
      {kind === 'fermentables' && (
        <>
          <label className="block text-sm">Type
            <select className={`${input} mt-1 w-full`} value={draft.type} onChange={set('type')}><option value="grain">grain</option><option value="extract">extract</option><option value="sugar">sugar</option><option value="adjunct">adjunct</option></select>
          </label>
          {field('ppg', 'PPG (0–50)', 'number')}
          {field('color_lovibond', 'Color (°L, 0–700)', 'number')}
          <label className="block text-sm">Default addition
            <select className={`${input} mt-1 w-full`} value={draft.default_addition} onChange={set('default_addition')}><option value="mash">mash</option><option value="steep">steep</option><option value="boil">boil</option><option value="fermenter">fermenter</option></select>
          </label>
        </>
      )}
      {kind === 'hops' && (<>{field('alpha_typical_pct', 'Typical alpha acid (%)', 'number')}{field('origin', 'Origin (optional)')}</>)}
      {kind === 'yeasts' && (<>{field('lab', 'Lab')}{field('product_code', 'Product code (optional)')}{field('attenuation_min_pct', 'Attenuation min (%)', 'number')}{field('attenuation_max_pct', 'Attenuation max (%)', 'number')}</>)}
      {save.isError && <p role="alert" className="text-sm text-red-800">{(save.error as Error).message}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending} className="rounded bg-amber-600 px-3 py-1 text-sm text-white disabled:opacity-50">{item ? 'Save' : 'Add'}</button>
        {item && <button type="button" className="px-3 py-1 text-sm" onClick={onDone}>Cancel</button>}
      </div>
    </form>
  )
}
