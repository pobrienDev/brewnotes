import { describe, expect, it } from 'vitest'

import { formatMeasure, galToL, hopWeight, kgToLb, lbToKg, srmColor, trim, volume, weight } from './units'

describe('units', () => {
  it('uses the exact plan constants', () => {
    expect(lbToKg(1)).toBe(0.45359237)
    expect(galToL(1)).toBe(3.785411784)
    expect(kgToLb(lbToKg(10))).toBeCloseTo(10, 12)
  })

  it('formats for the chosen system', () => {
    expect(formatMeasure(weight(lbToKg(10), 'imperial'))).toBe('10 lb')
    expect(formatMeasure(weight(4.536, 'metric'), 3)).toBe('4.536 kg')
    expect(formatMeasure(volume(galToL(5.5), 'imperial'))).toBe('5.5 gal')
    expect(formatMeasure(hopWeight(28.349523125, 'imperial'))).toBe('1 oz')
  })

  it('trims trailing zeros and handles non-finite values', () => {
    expect(trim(1.5)).toBe('1.5')
    expect(trim(2)).toBe('2')
    expect(trim(Number.NaN)).toBe('–')
  })

  it('clamps the SRM swatch lookup', () => {
    expect(srmColor(0)).toBe(srmColor(1))
    expect(srmColor(8.1)).toBe('#EA8F00')
    expect(srmColor(99)).toBe(srmColor(40))
  })
})
