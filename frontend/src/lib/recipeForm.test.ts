import { describe, expect, it } from 'vitest'

import { convertForm, emptyFermentable, emptyHop, emptyRecipe, fromApiBody, toApiBody } from './recipeForm'

describe('recipe form conversion', () => {
  it('converts imperial form values to a metric body and back', () => {
    const form = emptyRecipe('imperial')
    form.name = 'APA'
    form.fermentables = [{ ...emptyFermentable(), name: '2-row', amount: 10, ppg: 37, color_lovibond: 2 }]
    form.hops = [{ ...emptyHop(), name: 'Cascade', amount: 1, alpha_pct: 6.5, time_min: 60 }]
    const body = toApiBody(form, 'imperial')
    expect(body).not.toBeNull()
    expect(body!.batch_volume_l).toBeCloseTo(20.8198, 3)
    expect(body!.fermentables[0].amount_kg).toBeCloseTo(4.5359, 3)
    expect(body!.hops[0].amount_g).toBeCloseTo(28.3495, 3)
    expect(body!.hops[0].dry_hop_days).toBeNull()
    const back = fromApiBody(body!, 'imperial')
    expect(back.batch_volume).toBe(5.5)
    expect(back.fermentables[0].amount).toBe(10)
    expect(back.hops[0].amount).toBe(1)
  })

  it('is incomplete while required numbers are blank', () => {
    const form = emptyRecipe('metric')
    form.hops = [{ ...emptyHop(), name: 'Citra', amount: 30, alpha_pct: 12, use: 'dry_hop', time_min: '' }]
    expect(toApiBody(form, 'metric')).toBeNull()
    form.hops[0].dry_hop_days = 3
    expect(toApiBody(form, 'metric')?.hops[0]).toMatchObject({ time_min: null, dry_hop_days: 3 })
  })

  it('switches unit systems without changing the stored quantities', () => {
    const imperial = emptyRecipe('imperial')
    imperial.fermentables = [{ ...emptyFermentable(), name: 'malt', amount: 10, ppg: 37, color_lovibond: 2 }]
    const metric = convertForm(imperial, 'imperial', 'metric')
    expect(metric.batch_volume).toBeCloseTo(20.82, 2)
    expect(metric.fermentables[0].amount).toBeCloseTo(4.536, 3)
    const roundTrip = convertForm(metric, 'metric', 'imperial')
    expect(roundTrip.fermentables[0].amount).toBeCloseTo(10, 3)
  })
})
