import { describe, expect, it } from 'vitest'

import { attenuationProgressPct, chartSeries, nextStatus } from './batches'

describe('batch status workflow', () => {
  it('advances along the plan order and stops at done', () => {
    expect(nextStatus('planned')).toBe('fermenting')
    expect(nextStatus('fermenting')).toBe('conditioning')
    expect(nextStatus('conditioning')).toBe('packaged')
    expect(nextStatus('packaged')).toBe('done')
    expect(nextStatus('done')).toBeNull()
  })
})

describe('chart series', () => {
  const readings = [
    { id: 'a', taken_at: '2026-09-01T18:00:00Z', gravity_sg: 1.055, temp_c: 20, source: 'manual' as const, created_at: '' },
    { id: 'b', taken_at: '2026-09-02T18:00:00Z', gravity_sg: null, temp_c: 19, source: 'manual' as const, created_at: '' },
    { id: 'c', taken_at: '2026-09-03T18:00:00Z', gravity_sg: 1.02, temp_c: null, source: 'manual' as const, created_at: '' },
  ]

  it('keeps gaps as null and converts temperatures for display', () => {
    const imperial = chartSeries(readings, 'imperial')
    expect(imperial.gravity.map((p) => p.y)).toEqual([1.055, null, 1.02])
    expect(imperial.temperature.map((p) => p.y)).toEqual([68, 66.2, null])
    expect(imperial.temperatureUnit).toBe('°F')
    const metric = chartSeries(readings, 'metric')
    expect(metric.temperature.map((p) => p.y)).toEqual([20, 19, null])
    expect(metric.gravity[0].x).toBe('2026-09-01T18:00:00Z')
  })
})

describe('attenuation progress', () => {
  const base = {
    og: 1.055, og_source: 'estimated' as const, current_sg: 1.03, current_sg_source: 'reading' as const,
    expected_fg: 1.014, expected_attenuation_pct: 75, readings_count: 2, latest_reading_at: null, abv: 3.3,
  }
  it('is the share of the expected attenuation, clamped to 0–100', () => {
    expect(attenuationProgressPct({ ...base, apparent_attenuation_pct: 37.5 })).toBe(50)
    expect(attenuationProgressPct({ ...base, apparent_attenuation_pct: 90 })).toBe(100)
    expect(attenuationProgressPct({ ...base, apparent_attenuation_pct: null })).toBeNull()
    expect(attenuationProgressPct({ ...base, apparent_attenuation_pct: 10, expected_attenuation_pct: null })).toBeNull()
  })
})
