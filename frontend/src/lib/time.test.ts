import { describe, expect, it } from 'vitest'

import { fromLocalInputValue, toLocalInputValue } from './time'

describe('datetime-local round trip', () => {
  it('formats a date in local time for the input and parses it back to the same instant', () => {
    const instant = new Date(2026, 8, 1, 18, 30) // local time
    const value = toLocalInputValue(instant)
    expect(value).toBe('2026-09-01T18:30')
    expect(fromLocalInputValue(value)).toBe(instant.toISOString())
  })
  it('treats blank and garbage as no value', () => {
    expect(fromLocalInputValue('')).toBeNull()
    expect(fromLocalInputValue('not a date')).toBeNull()
  })
})
