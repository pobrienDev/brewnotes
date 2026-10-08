/**
 * The recipe editor keeps its values in the user's display units; these helpers convert to
 * and from the API's metric body. No brewing math here, only unit conversion.
 */
import type { components } from '../api/schema'
import {
  type UnitSystem,
  hopWeight,
  toStoredHopWeight,
  toStoredVolume,
  toStoredWeight,
  volume,
  weight,
} from './units'

export type RecipeWrite = components['schemas']['RecipeWrite']
export type RecipeOut = components['schemas']['RecipeOut']
export type RecipeInput = components['schemas']['RecipeInput']
export type FermentableType = components['schemas']['RecipeFermentableInput']['type']
export type Addition = components['schemas']['RecipeFermentableInput']['addition']
export type HopUse = components['schemas']['RecipeHopInput']['use']

export interface FermentableRow {
  name: string
  type: FermentableType
  addition: Addition
  amount: number | ''
  ppg: number | ''
  color_lovibond: number | ''
  fermentable_id: string | null
}
export interface HopRow {
  name: string
  amount: number | ''
  alpha_pct: number | ''
  use: HopUse
  time_min: number | ''
  dry_hop_days: number | ''
  hop_id: string | null
}
export interface YeastRow {
  name: string
  attenuation_pct: number | ''
  yeast_id: string | null
}
export interface RecipeForm {
  name: string
  notes: string
  target_style: string
  batch_volume: number | ''
  pre_boil_volume: number | ''
  boil_time_min: number | ''
  brewhouse_efficiency_pct: number | ''
  steep_efficiency_pct: number | ''
  fermentables: FermentableRow[]
  hops: HopRow[]
  yeasts: YeastRow[]
}

const num = (v: number | '') => (v === '' ? Number.NaN : Number(v))

export function emptyRecipe(system: UnitSystem): RecipeForm {
  return {
    name: '',
    notes: '',
    target_style: '',
    batch_volume: system === 'imperial' ? 5.5 : 20,
    pre_boil_volume: '',
    boil_time_min: 60,
    brewhouse_efficiency_pct: 72,
    steep_efficiency_pct: 50,
    fermentables: [],
    hops: [],
    yeasts: [],
  }
}

export const emptyFermentable = (): FermentableRow => ({
  name: '',
  type: 'grain',
  addition: 'mash',
  amount: '',
  ppg: '',
  color_lovibond: '',
  fermentable_id: null,
})
export const emptyHop = (): HopRow => ({
  name: '',
  amount: '',
  alpha_pct: '',
  use: 'boil',
  time_min: 60,
  dry_hop_days: '',
  hop_id: null,
})
export const emptyYeast = (): YeastRow => ({ name: '', attenuation_pct: 75, yeast_id: null })

/** Metric API body from the form. Returns null while required numbers are still blank. */
export function toApiBody(form: RecipeForm, system: UnitSystem): RecipeWrite | null {
  const batch = num(form.batch_volume)
  const boil = num(form.boil_time_min)
  if (!Number.isFinite(batch) || !Number.isFinite(boil)) return null
  const fermentables: RecipeWrite['fermentables'] = []
  for (const f of form.fermentables) {
    const amount = num(f.amount)
    const ppg = num(f.ppg)
    const color = num(f.color_lovibond)
    if (!f.name || !Number.isFinite(amount) || !Number.isFinite(ppg) || !Number.isFinite(color)) return null
    fermentables.push({
      name: f.name,
      type: f.type,
      addition: f.addition,
      amount_kg: toStoredWeight(amount, system),
      ppg,
      color_lovibond: color,
      fermentable_id: f.fermentable_id,
    })
  }
  const hops: RecipeWrite['hops'] = []
  for (const h of form.hops) {
    const amount = num(h.amount)
    const alpha = num(h.alpha_pct)
    if (!h.name || !Number.isFinite(amount) || !Number.isFinite(alpha)) return null
    const needsTime = h.use === 'boil' || h.use === 'whirlpool'
    const time = num(h.time_min)
    const days = num(h.dry_hop_days)
    if (needsTime && !Number.isFinite(time)) return null
    if (h.use === 'dry_hop' && !Number.isFinite(days)) return null
    hops.push({
      name: h.name,
      amount_g: toStoredHopWeight(amount, system),
      alpha_pct: alpha,
      use: h.use,
      time_min: needsTime ? time : null,
      dry_hop_days: h.use === 'dry_hop' ? days : null,
      hop_id: h.hop_id,
    })
  }
  const yeasts: RecipeWrite['yeasts'] = []
  for (const y of form.yeasts) {
    const att = num(y.attenuation_pct)
    if (!y.name || !Number.isFinite(att)) return null
    yeasts.push({ name: y.name, attenuation_pct: att, yeast_id: y.yeast_id })
  }
  const pre = num(form.pre_boil_volume)
  return {
    name: form.name || 'Untitled recipe',
    notes: form.notes,
    target_style: form.target_style || null,
    batch_volume_l: toStoredVolume(batch, system),
    pre_boil_volume_l: Number.isFinite(pre) ? toStoredVolume(pre, system) : null,
    boil_time_min: boil,
    brewhouse_efficiency_pct: num(form.brewhouse_efficiency_pct) || 72,
    steep_efficiency_pct: num(form.steep_efficiency_pct) || 50,
    fermentables,
    hops,
    yeasts,
  }
}

const round = (v: number, digits: number) => Number(v.toFixed(digits))

/** Display-unit form values from a saved recipe (or a scaled body). */
export function fromApiBody(body: RecipeWrite | RecipeOut, system: UnitSystem): RecipeForm {
  const targetStyle =
    'target_style' in body && body.target_style && typeof body.target_style === 'object'
      ? body.target_style.slug
      : ((body.target_style as string | null | undefined) ?? '')
  return {
    name: body.name,
    notes: body.notes,
    target_style: targetStyle ?? '',
    batch_volume: round(volume(body.batch_volume_l, system).value, 3),
    pre_boil_volume:
      body.pre_boil_volume_l == null ? '' : round(volume(body.pre_boil_volume_l, system).value, 3),
    boil_time_min: body.boil_time_min,
    brewhouse_efficiency_pct: body.brewhouse_efficiency_pct,
    steep_efficiency_pct: body.steep_efficiency_pct,
    fermentables: body.fermentables.map((f) => ({
      name: f.name,
      type: f.type,
      addition: f.addition,
      amount: round(weight(f.amount_kg, system).value, 3),
      ppg: f.ppg,
      color_lovibond: f.color_lovibond,
      fermentable_id: f.fermentable_id ?? null,
    })),
    hops: body.hops.map((h) => ({
      name: h.name,
      amount: round(hopWeight(h.amount_g, system).value, 3),
      alpha_pct: h.alpha_pct,
      use: h.use,
      time_min: h.time_min ?? '',
      dry_hop_days: h.dry_hop_days ?? '',
      hop_id: h.hop_id ?? null,
    })),
    yeasts: body.yeasts.map((y) => ({
      name: y.name,
      attenuation_pct: y.attenuation_pct,
      yeast_id: y.yeast_id ?? null,
    })),
  }
}

/** Re-express a form in another unit system without touching the API. */
export function convertForm(form: RecipeForm, from: UnitSystem, to: UnitSystem): RecipeForm {
  if (from === to) return form
  const body = toApiBody(form, from)
  if (!body) return form
  const converted = fromApiBody(body, to)
  return { ...converted, name: form.name, notes: form.notes }
}

const DRAFT_KEY = 'brewnotes.draft'

export function saveDraft(form: RecipeForm, system: UnitSystem): void {
  try {
    window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ form, system }))
  } catch {
    // no session storage: the draft is simply not kept across the redirect
  }
}

export function takeDraft(): { form: RecipeForm; system: UnitSystem } | null {
  try {
    const raw = window.sessionStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    window.sessionStorage.removeItem(DRAFT_KEY)
    return JSON.parse(raw) as { form: RecipeForm; system: UnitSystem }
  } catch {
    return null
  }
}
