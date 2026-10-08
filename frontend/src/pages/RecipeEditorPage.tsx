import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef } from 'react'
import { type UseFormReturn, useFieldArray, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { CatalogPicker } from '../components/CatalogPicker'
import { ScaleDialog } from '../components/ScaleDialog'
import { StatsPanel } from '../components/StatsPanel'
import { StyleMatchPanel } from '../components/StyleMatchPanel'
import type { CatalogItem } from '../hooks/useCatalog'
import { useMe } from '../hooks/useMe'
import { useRecipeCalc } from '../hooks/useRecipeCalc'
import { useAllStyles } from '../hooks/useStyles'
import { useUnitSystem } from '../hooks/useUnitSystem'
import { describeProblem } from '../lib/problem'
import {
  type RecipeForm,
  type RecipeOut,
  type RecipeWrite,
  convertForm,
  emptyFermentable,
  emptyHop,
  emptyRecipe,
  emptyYeast,
  fromApiBody,
  saveDraft,
  takeDraft,
  toApiBody,
} from '../lib/recipeForm'
import type { UnitSystem } from '../lib/units'

type RecipeInput = components['schemas']['RecipeInput']

/** The calculator takes the bare recipe body: no name, notes, ids or fermentable types. */
function toCalcInput(body: RecipeWrite): RecipeInput {
  return {
    batch_volume_l: body.batch_volume_l,
    pre_boil_volume_l: body.pre_boil_volume_l,
    boil_time_min: body.boil_time_min,
    brewhouse_efficiency_pct: body.brewhouse_efficiency_pct,
    steep_efficiency_pct: body.steep_efficiency_pct,
    target_style: body.target_style,
    fermentables: body.fermentables.map(({ name, amount_kg, ppg, color_lovibond, addition }) => ({
      name,
      amount_kg,
      ppg,
      color_lovibond,
      addition,
    })),
    hops: body.hops.map(({ name, amount_g, alpha_pct, use, time_min, dry_hop_days }) => ({
      name,
      amount_g,
      alpha_pct,
      use,
      time_min,
      dry_hop_days,
    })),
    yeasts: body.yeasts.map(({ name, attenuation_pct }) => ({ name, attenuation_pct })),
  }
}

/** Apply a scaled body to the current form, keeping names, types and catalog references. */
function applyScaled(current: RecipeForm, scaled: RecipeInput, system: UnitSystem): RecipeForm {
  const write: RecipeWrite = {
    ...scaled,
    name: current.name,
    notes: current.notes,
    fermentables: scaled.fermentables.map((f, i) => ({
      ...f,
      type: current.fermentables[i]?.type ?? 'grain',
      fermentable_id: current.fermentables[i]?.fermentable_id ?? null,
    })),
    hops: scaled.hops.map((h, i) => ({ ...h, hop_id: current.hops[i]?.hop_id ?? null })),
    yeasts: scaled.yeasts.map((y, i) => ({ ...y, yeast_id: current.yeasts[i]?.yeast_id ?? null })),
  }
  return fromApiBody(write, system)
}

const input = 'w-full rounded border border-stone-300 px-2 py-1'
const numberField = { valueAsNumber: true as const }

export function RecipeEditorPage() {
  const { id } = useParams()
  const me = useMe()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [system, setSystem] = useUnitSystem()
  const styles = useAllStyles()
  const form = useForm<RecipeForm>({ defaultValues: emptyRecipe(system) })
  const loadedFor = useRef<string | null>(null)

  const existing = useQuery({
    queryKey: ['recipe', id],
    enabled: Boolean(id),
    queryFn: async (): Promise<RecipeOut> => {
      const { data, error, response } = await api.GET('/api/v1/recipes/{recipe_id}', {
        params: { path: { recipe_id: id! } },
      })
      if (!data) throw new Error(response.status === 404 ? 'Recipe not found' : describeProblem(error))
      return data
    },
  })

  // Load the saved recipe, or restore a draft kept across the sign-in redirect.
  useEffect(() => {
    if (id && existing.data && loadedFor.current !== id) {
      form.reset(fromApiBody(existing.data, system))
      loadedFor.current = id
    } else if (!id && loadedFor.current !== 'new') {
      const draft = takeDraft()
      if (draft) form.reset(convertForm(draft.form, draft.system, system))
      loadedFor.current = 'new'
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, existing.data])

  const values = useWatch({ control: form.control }) as RecipeForm
  const body = useMemo(() => toApiBody(values, system), [values, system])
  const calcInput = useMemo(() => (body ? toCalcInput(body) : null), [body])
  const calc = useRecipeCalc(calcInput)

  const switchUnits = (next: UnitSystem) => {
    form.reset(convertForm(form.getValues(), system, next))
    setSystem(next)
  }

  const save = useMutation({
    mutationFn: async (write: RecipeWrite) => {
      const result = id
        ? await api.PUT('/api/v1/recipes/{recipe_id}', { params: { path: { recipe_id: id } }, body: write })
        : await api.POST('/api/v1/recipes', { body: write })
      if (!result.data) throw new Error(describeProblem(result.error, `Save failed (${result.response.status})`))
      return result.data
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ['recipes'] })
      queryClient.setQueryData(['recipe', saved.id], saved)
      loadedFor.current = saved.id
      void navigate(`/recipes/${saved.id}`, { replace: true })
    },
  })

  const remove = useMutation({
    mutationFn: async () => {
      const { response } = await api.DELETE('/api/v1/recipes/{recipe_id}', { params: { path: { recipe_id: id! } } })
      if (!response.ok) throw new Error(`Delete failed (${response.status})`)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['recipes'] })
      void navigate('/recipes')
    },
  })

  const onSave = form.handleSubmit((current) => {
    const write = toApiBody(current, system)
    if (!write) return
    if (!me.data) {
      saveDraft(current, system)
      void navigate('/sign-in?next=/recipes/new')
      return
    }
    save.mutate(write)
  })

  if (id && existing.isError) {
    return (
      <p role="alert" className="text-red-800">
        {(existing.error as Error).message}. <Link to="/recipes" className="underline">Back to recipes</Link>
      </p>
    )
  }

  const w = system === 'imperial' ? 'lb' : 'kg'
  const hw = system === 'imperial' ? 'oz' : 'g'
  const vol = system === 'imperial' ? 'gal' : 'L'

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <header className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">{id ? 'Edit recipe' : 'Recipe designer'}</h1>
          <span className="flex-1" />
          <fieldset className="flex items-center gap-1 text-sm">
            <legend className="sr-only">Display units</legend>
            {(['imperial', 'metric'] as const).map((s) => (
              <label key={s} className={`cursor-pointer rounded px-2 py-1 ${system === s ? 'bg-amber-100' : ''}`}>
                <input type="radio" name="units" className="sr-only" checked={system === s} onChange={() => switchUnits(s)} />
                {s === 'imperial' ? 'US' : 'Metric'}
              </label>
            ))}
          </fieldset>
          <ScaleDialog
            body={calcInput}
            system={system}
            onApply={(scaled) => form.reset(applyScaled(form.getValues(), scaled, system))}
          />
          <button type="submit" form="recipe-form" disabled={save.isPending || !body} className="rounded bg-amber-600 px-3 py-1 text-white hover:bg-amber-700 disabled:opacity-50">
            {me.data ? (id ? 'Save changes' : 'Save recipe') : 'Sign in to save'}
          </button>
        </header>
        {save.isError && <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">{(save.error as Error).message}</p>}

        <form id="recipe-form" onSubmit={onSave} className="space-y-6">
        <section className="grid gap-3 md:grid-cols-2">
          <label className="text-sm md:col-span-2">
            Name
            <input className={input} {...form.register('name', { maxLength: 200 })} placeholder="My pale ale" />
          </label>
          <label className="text-sm md:col-span-2">
            Target style
            <select className={input} {...form.register('target_style')}>
              <option value="">None</option>
              {styles.data?.map((s) => (
                <option key={s.slug} value={s.slug}>
                  {s.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Batch volume ({vol})
            <input type="number" step="any" className={input} {...form.register('batch_volume', numberField)} />
          </label>
          <label className="text-sm">
            Pre-boil volume ({vol}, optional)
            <input type="number" step="any" className={input} {...form.register('pre_boil_volume', numberField)} />
          </label>
          <label className="text-sm">
            Boil time (min)
            <input type="number" step="any" className={input} {...form.register('boil_time_min', numberField)} />
          </label>
          <label className="text-sm">
            Brewhouse efficiency (%)
            <input type="number" step="any" className={input} {...form.register('brewhouse_efficiency_pct', numberField)} />
          </label>
          <label className="text-sm">
            Steep efficiency (%)
            <input type="number" step="any" className={input} {...form.register('steep_efficiency_pct', numberField)} />
          </label>
        </section>

        <FermentablesTable form={form} weightUnit={w} />
        <HopsTable form={form} weightUnit={hw} />
        <YeastsTable form={form} />

        <label className="block text-sm">
          Notes
          <textarea className={`${input} min-h-24`} {...form.register('notes', { maxLength: 10_000 })} />
        </label>
        </form>

        {id && (
          <button
            type="button"
            className="text-sm text-red-800 hover:underline"
            onClick={() => {
              if (window.confirm('Delete this recipe? This cannot be undone.')) remove.mutate()
            }}
          >
            Delete recipe
          </button>
        )}
      </div>

      <aside className="space-y-4">
        <StatsPanel
          stats={calc.data?.stats}
          notes={calc.data?.notes}
          error={calc.isError ? (calc.error as Error).message : undefined}
        />
        <StyleMatchPanel matches={calc.data?.style_matches ?? []} targetSlug={values.target_style || null} />
      </aside>
    </div>
  )
}

function RowButtons({ onUp, onDown, onRemove }: { onUp?: () => void; onDown?: () => void; onRemove: () => void }) {
  return (
    <span className="flex gap-1">
      <button type="button" aria-label="Move up" disabled={!onUp} onClick={onUp} className="px-1 disabled:opacity-30">↑</button>
      <button type="button" aria-label="Move down" disabled={!onDown} onClick={onDown} className="px-1 disabled:opacity-30">↓</button>
      <button type="button" aria-label="Remove" onClick={onRemove} className="px-1 text-red-800">✕</button>
    </span>
  )
}

function FermentablesTable({ form, weightUnit }: { form: UseFormReturn<RecipeForm>; weightUnit: string }) {
  const rows = useFieldArray({ control: form.control, name: 'fermentables' })
  return (
    <section>
      <header className="mb-1 flex items-center justify-between">
        <h2 className="font-semibold">Fermentables</h2>
        <button type="button" className="text-sm text-amber-700 hover:underline" onClick={() => rows.append(emptyFermentable())}>
          Add fermentable
        </button>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="min-w-48">Name</th><th>Type</th><th>Addition</th><th>Amount ({weightUnit})</th><th>PPG</th><th>Color (°L)</th><th /></tr>
          </thead>
          <tbody>
            {rows.fields.map((field, i) => (
              <tr key={field.id} className="border-t border-stone-100">
                <td className="py-1 pr-1">
                  <CatalogPicker
                    kind="fermentables"
                    label={`Fermentable ${i + 1} name`}
                    value={form.watch(`fermentables.${i}.name`)}
                    onChange={(name) => form.setValue(`fermentables.${i}.name`, name)}
                    onPick={(item: CatalogItem) => {
                      if (!('ppg' in item)) return
                      form.setValue(`fermentables.${i}.name`, item.name)
                      form.setValue(`fermentables.${i}.type`, item.type)
                      form.setValue(`fermentables.${i}.addition`, item.default_addition)
                      form.setValue(`fermentables.${i}.ppg`, item.ppg)
                      form.setValue(`fermentables.${i}.color_lovibond`, item.color_lovibond)
                      form.setValue(`fermentables.${i}.fermentable_id`, item.id)
                    }}
                  />
                </td>
                <td className="py-1 pr-1">
                  <select aria-label="Type" className={input} {...form.register(`fermentables.${i}.type`)}>
                    <option value="grain">grain</option><option value="extract">extract</option><option value="sugar">sugar</option><option value="adjunct">adjunct</option>
                  </select>
                </td>
                <td className="py-1 pr-1">
                  <select aria-label="Addition" className={input} {...form.register(`fermentables.${i}.addition`)}>
                    <option value="mash">mash</option><option value="steep">steep</option><option value="boil">boil</option><option value="fermenter">fermenter</option>
                  </select>
                </td>
                <td className="py-1 pr-1"><input aria-label="Amount" type="number" step="any" className={input} {...form.register(`fermentables.${i}.amount`, numberField)} /></td>
                <td className="py-1 pr-1"><input aria-label="PPG" type="number" step="any" className={input} {...form.register(`fermentables.${i}.ppg`, numberField)} /></td>
                <td className="py-1 pr-1"><input aria-label="Color" type="number" step="any" className={input} {...form.register(`fermentables.${i}.color_lovibond`, numberField)} /></td>
                <td className="py-1">
                  <RowButtons onUp={i > 0 ? () => rows.swap(i, i - 1) : undefined} onDown={i < rows.fields.length - 1 ? () => rows.swap(i, i + 1) : undefined} onRemove={() => rows.remove(i)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function HopsTable({ form, weightUnit }: { form: UseFormReturn<RecipeForm>; weightUnit: string }) {
  const rows = useFieldArray({ control: form.control, name: 'hops' })
  return (
    <section>
      <header className="mb-1 flex items-center justify-between">
        <h2 className="font-semibold">Hops</h2>
        <button type="button" className="text-sm text-amber-700 hover:underline" onClick={() => rows.append(emptyHop())}>
          Add hop
        </button>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="min-w-48">Name</th><th>Amount ({weightUnit})</th><th>Alpha (%)</th><th>Use</th><th>Time (min) / Days</th><th /></tr>
          </thead>
          <tbody>
            {rows.fields.map((field, i) => {
              const use = form.watch(`hops.${i}.use`)
              return (
                <tr key={field.id} className="border-t border-stone-100">
                  <td className="py-1 pr-1">
                    <CatalogPicker
                      kind="hops"
                      label={`Hop ${i + 1} name`}
                      value={form.watch(`hops.${i}.name`)}
                      onChange={(name) => form.setValue(`hops.${i}.name`, name)}
                      onPick={(item: CatalogItem) => {
                        if (!('alpha_typical_pct' in item)) return
                        form.setValue(`hops.${i}.name`, item.name)
                        form.setValue(`hops.${i}.alpha_pct`, item.alpha_typical_pct)
                        form.setValue(`hops.${i}.hop_id`, item.id)
                      }}
                    />
                  </td>
                  <td className="py-1 pr-1"><input aria-label="Amount" type="number" step="any" className={input} {...form.register(`hops.${i}.amount`, numberField)} /></td>
                  <td className="py-1 pr-1"><input aria-label="Alpha acid" type="number" step="any" className={input} {...form.register(`hops.${i}.alpha_pct`, numberField)} /></td>
                  <td className="py-1 pr-1">
                    <select aria-label="Use" className={input} {...form.register(`hops.${i}.use`)}>
                      <option value="boil">boil</option><option value="first_wort">first wort</option><option value="whirlpool">whirlpool</option><option value="dry_hop">dry hop</option>
                    </select>
                  </td>
                  <td className="py-1 pr-1">
                    {use === 'dry_hop' ? (
                      <input aria-label="Dry hop days" type="number" step="any" className={input} {...form.register(`hops.${i}.dry_hop_days`, numberField)} />
                    ) : use === 'first_wort' ? (
                      <span className="text-stone-500">full boil</span>
                    ) : (
                      <input aria-label="Boil minutes" type="number" step="any" className={input} {...form.register(`hops.${i}.time_min`, numberField)} />
                    )}
                  </td>
                  <td className="py-1">
                    <RowButtons onUp={i > 0 ? () => rows.swap(i, i - 1) : undefined} onDown={i < rows.fields.length - 1 ? () => rows.swap(i, i + 1) : undefined} onRemove={() => rows.remove(i)} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function YeastsTable({ form }: { form: UseFormReturn<RecipeForm> }) {
  const rows = useFieldArray({ control: form.control, name: 'yeasts' })
  return (
    <section>
      <header className="mb-1 flex items-center justify-between">
        <h2 className="font-semibold">Yeast</h2>
        <button type="button" className="text-sm text-amber-700 hover:underline" onClick={() => rows.append(emptyYeast())}>
          Add yeast
        </button>
      </header>
      <table className="w-full text-sm">
        <thead className="text-left text-stone-500">
          <tr><th className="min-w-48">Name</th><th>Attenuation (%)</th><th /></tr>
        </thead>
        <tbody>
          {rows.fields.map((field, i) => (
            <tr key={field.id} className="border-t border-stone-100">
              <td className="py-1 pr-1">
                <CatalogPicker
                  kind="yeasts"
                  label={`Yeast ${i + 1} name`}
                  value={form.watch(`yeasts.${i}.name`)}
                  onChange={(name) => form.setValue(`yeasts.${i}.name`, name)}
                  onPick={(item: CatalogItem) => {
                    if (!('attenuation_midpoint_pct' in item)) return
                    form.setValue(`yeasts.${i}.name`, item.name)
                    form.setValue(`yeasts.${i}.attenuation_pct`, item.attenuation_midpoint_pct)
                    form.setValue(`yeasts.${i}.yeast_id`, item.id)
                  }}
                />
              </td>
              <td className="py-1 pr-1"><input aria-label="Attenuation" type="number" step="any" className={input} {...form.register(`yeasts.${i}.attenuation_pct`, numberField)} /></td>
              <td className="py-1">
                <RowButtons onUp={i > 0 ? () => rows.swap(i, i - 1) : undefined} onDown={i < rows.fields.length - 1 ? () => rows.swap(i, i + 1) : undefined} onRemove={() => rows.remove(i)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.fields.length === 0 && <p className="text-xs text-stone-500">Without a yeast, 75% attenuation is assumed.</p>}
    </section>
  )
}
