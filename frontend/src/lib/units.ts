/**
 * Display-only unit conversion. The backend stores metric (kg, g, L, °C) and does all brewing
 * math; the only arithmetic allowed here is converting a stored value for display and back,
 * using the exact constants from the plan (Section 7).
 */

export const KG_PER_LB = 0.45359237
export const L_PER_US_GAL = 3.785411784
export const G_PER_OZ = 28.349523125

export type UnitSystem = 'metric' | 'imperial'

export const kgToLb = (kg: number) => kg / KG_PER_LB
export const lbToKg = (lb: number) => lb * KG_PER_LB
export const lToGal = (l: number) => l / L_PER_US_GAL
export const galToL = (gal: number) => gal * L_PER_US_GAL
export const gToOz = (g: number) => g / G_PER_OZ
export const ozToG = (oz: number) => oz * G_PER_OZ
export const cToF = (c: number) => (c * 9) / 5 + 32
export const fToC = (f: number) => ((f - 32) * 5) / 9

export interface Measure {
  /** Value in the display unit. */
  value: number
  unit: string
}

/** Fermentable weight: kg stored, lb or kg shown. */
export function weight(kg: number, system: UnitSystem): Measure {
  return system === 'imperial' ? { value: kgToLb(kg), unit: 'lb' } : { value: kg, unit: 'kg' }
}

/** Hop weight: g stored, oz or g shown. */
export function hopWeight(g: number, system: UnitSystem): Measure {
  return system === 'imperial' ? { value: gToOz(g), unit: 'oz' } : { value: g, unit: 'g' }
}

/** Volume: L stored, gal or L shown. */
export function volume(l: number, system: UnitSystem): Measure {
  return system === 'imperial' ? { value: lToGal(l), unit: 'gal' } : { value: l, unit: 'L' }
}

export function temperature(c: number, system: UnitSystem): Measure {
  return system === 'imperial' ? { value: cToF(c), unit: '°F' } : { value: c, unit: '°C' }
}

/** Back to storage units from what the user typed in the display unit. */
export const toStoredWeight = (value: number, system: UnitSystem) =>
  system === 'imperial' ? lbToKg(value) : value
export const toStoredHopWeight = (value: number, system: UnitSystem) =>
  system === 'imperial' ? ozToG(value) : value
export const toStoredVolume = (value: number, system: UnitSystem) =>
  system === 'imperial' ? galToL(value) : value

export function formatMeasure(m: Measure, digits = 2): string {
  return `${trim(m.value, digits)} ${m.unit}`
}

/** Fixed digits without trailing zeros: 1.5000 -> "1.5", 2 -> "2". */
export function trim(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return '–'
  return Number(value.toFixed(digits)).toString()
}

export const formatGravity = (sg: number) => sg.toFixed(3)
export const formatPercent = (pct: number, digits = 1) => `${trim(pct, digits)}%`

/**
 * Standard SRM to display colour lookup (1 to 40). Every swatch also shows the number, so
 * colour is never the only signal.
 */
const SRM_RGB: Record<number, string> = {
  1: '#FFE699', 2: '#FFD878', 3: '#FFCA5A', 4: '#FFBF42', 5: '#FBB123', 6: '#F8A600',
  7: '#F39C00', 8: '#EA8F00', 9: '#E58500', 10: '#DE7C00', 11: '#D77200', 12: '#CF6900',
  13: '#CB6200', 14: '#C35900', 15: '#BB5100', 16: '#B54C00', 17: '#B04500', 18: '#A63E00',
  19: '#A13700', 20: '#9B3200', 21: '#952D00', 22: '#8E2900', 23: '#882300', 24: '#821E00',
  25: '#7B1A00', 26: '#771900', 27: '#701400', 28: '#6A0E00', 29: '#660D00', 30: '#5E0B00',
  31: '#5A0A02', 32: '#600903', 33: '#520907', 34: '#4C0505', 35: '#470606', 36: '#440607',
  37: '#3F0708', 38: '#3B0607', 39: '#3A070B', 40: '#36080A',
}

export function srmColor(srm: number): string {
  const key = Math.min(40, Math.max(1, Math.round(srm)))
  return SRM_RGB[key] ?? SRM_RGB[40]
}
