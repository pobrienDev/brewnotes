import type { components } from '../api/schema'
import { type UnitSystem, temperature } from './units'

export type BatchOut = components['schemas']['BatchOut']
export type BatchSummary = components['schemas']['BatchSummary']
export type BatchStatus = BatchOut['status']
export type ReadingOut = components['schemas']['ReadingOut']
export type FermentationOut = components['schemas']['FermentationOut']

/** The workflow in order (plan Section 6). Any status may be chosen; this is the usual path. */
export const STATUSES: readonly BatchStatus[] = ['planned', 'fermenting', 'conditioning', 'packaged', 'done']

export const STATUS_LABELS: Record<BatchStatus, string> = {
  planned: 'Planned',
  fermenting: 'Fermenting',
  conditioning: 'Conditioning',
  packaged: 'Packaged',
  done: 'Done',
}

export function nextStatus(status: BatchStatus): BatchStatus | null {
  const index = STATUSES.indexOf(status)
  return index >= 0 && index < STATUSES.length - 1 ? STATUSES[index + 1] : null
}

export interface ChartPoint {
  /** ISO timestamp; Chart.js's time scale parses it. */
  x: string
  y: number | null
}

export interface ChartSeries {
  gravity: ChartPoint[]
  temperature: ChartPoint[]
  temperatureUnit: string
}

/**
 * Readings (oldest first, as the ?points= endpoint returns them) as two chart series.
 * Temperatures are converted for display; gravity is dimensionless. Missing values stay
 * null so the chart draws a gap rather than a false zero.
 */
export function chartSeries(readings: ReadingOut[], system: UnitSystem): ChartSeries {
  const unit = temperature(0, system).unit
  return {
    gravity: readings.map((r) => ({ x: r.taken_at, y: r.gravity_sg })),
    temperature: readings.map((r) => ({
      x: r.taken_at,
      y: r.temp_c === null ? null : temperature(r.temp_c, system).value,
    })),
    temperatureUnit: unit,
  }
}

/** Share of the expected attenuation reached so far, clamped to 0–100 for a progress bar. */
export function attenuationProgressPct(f: FermentationOut): number | null {
  if (f.apparent_attenuation_pct === null || !f.expected_attenuation_pct) return null
  return Math.max(0, Math.min(100, (f.apparent_attenuation_pct / f.expected_attenuation_pct) * 100))
}
