import { describe, expect, it } from 'vitest'

import { RATING_VALUES, formatRating, isRating, ratingStars } from './rating'

describe('ratings', () => {
  it('runs from 0.5 to 5 in half steps', () => {
    expect(RATING_VALUES).toHaveLength(10)
    expect(isRating(3.5)).toBe(true)
    expect(isRating(3.3)).toBe(false)
    expect(isRating(0)).toBe(false)
  })
  it('renders as text that carries the value', () => {
    expect(formatRating(4.5)).toBe('4.5 / 5')
    expect(ratingStars(4.5)).toBe('★★★★½')
    expect(ratingStars(3)).toBe('★★★☆☆')
    expect(ratingStars(0.5)).toBe('½☆☆☆☆')
  })
})
