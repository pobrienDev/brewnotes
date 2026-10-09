/** Ratings run from 0.5 to 5 in half steps (plan Section 5). */
export const RATING_VALUES = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5] as const

export type Rating = (typeof RATING_VALUES)[number]

export const isRating = (value: number): value is Rating =>
  (RATING_VALUES as readonly number[]).includes(value)

/** "4.5 / 5" for lists and badges; the stars are decoration only. */
export const formatRating = (rating: number) => `${rating} / 5`

/** Full, half and empty stars as text so the value survives without colour or icons. */
export function ratingStars(rating: number): string {
  const full = Math.floor(rating)
  const half = rating - full >= 0.5 ? 1 : 0
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(5 - full - half)
}
