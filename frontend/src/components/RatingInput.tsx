import { RATING_VALUES, type Rating, formatRating, ratingStars } from '../lib/rating'

/** Ten radio buttons (0.5 to 5) shown as stars; each option is labelled with its number. */
export function RatingInput({
  value,
  onChange,
  name = 'rating',
}: {
  value: Rating | null
  onChange: (rating: Rating) => void
  name?: string
}) {
  return (
    <fieldset>
      <legend className="text-sm">
        Rating{' '}
        <span className="text-stone-600">{value === null ? '(choose 0.5 to 5)' : formatRating(value)}</span>
      </legend>
      <div className="mt-1 flex flex-wrap gap-1" role="radiogroup" aria-label="Rating">
        {RATING_VALUES.map((r) => (
          <label
            key={r}
            className={`cursor-pointer rounded border px-2 py-1 text-sm ${value === r ? 'border-amber-600 bg-amber-100' : 'border-stone-300 hover:bg-stone-100'}`}
          >
            <input
              type="radio"
              name={name}
              value={r}
              className="sr-only"
              checked={value === r}
              onChange={() => onChange(r)}
              aria-label={`${r} out of 5`}
            />
            {r}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export function RatingDisplay({ rating }: { rating: number }) {
  return (
    <span className="whitespace-nowrap">
      <span aria-hidden="true" className="text-amber-600">
        {ratingStars(rating)}
      </span>{' '}
      <span className="text-sm text-stone-700">{formatRating(rating)}</span>
    </span>
  )
}
