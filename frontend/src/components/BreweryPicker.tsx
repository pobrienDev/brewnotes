import { useId, useState } from 'react'

import { useBrewerySearch } from '../hooks/useBreweries'
import { type BreweryRef, formatPlace } from '../lib/map'

/**
 * Pick a brewery from the map data by name or city. The chosen brewery is shown with a clear
 * button; nothing is chosen until the user picks a suggestion.
 */
export function BreweryPicker({
  value,
  onChange,
  label = 'Brewery',
}: {
  value: BreweryRef | null
  onChange: (brewery: BreweryRef | null) => void
  label?: string
}) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const search = useBrewerySearch(text)
  const listId = useId()
  if (value) {
    return (
      <div className="text-sm">
        <span className="block">{label}</span>
        <span className="mt-1 inline-flex items-center gap-2 rounded border border-stone-300 bg-stone-50 px-2 py-1">
          <span>
            {value.name} <span className="text-stone-500">({formatPlace(value)})</span>
          </span>
          <button type="button" className="text-red-800 hover:underline" onClick={() => onChange(null)} aria-label={`Clear ${label.toLowerCase()}`}>
            clear
          </button>
        </span>
      </div>
    )
  }
  const suggestions = open && search.data ? search.data : []
  return (
    <div className="relative text-sm">
      <label className="block">
        {label}
        <input
          className="mt-1 w-full rounded border border-stone-300 px-2 py-1"
          value={text}
          onChange={(e) => { setText(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          placeholder="Search the map's breweries by name or city"
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={suggestions.length > 0}
        />
      </label>
      {suggestions.length > 0 && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded border border-stone-300 bg-white shadow">
          {suggestions.map((b) => (
            <li key={b.id} role="option" aria-selected={false}>
              <button type="button" className="flex w-full justify-between gap-2 px-2 py-1 text-left hover:bg-amber-50" onMouseDown={(e) => e.preventDefault()} onClick={() => { onChange(b); setText(''); setOpen(false) }}>
                <span>{b.name}</span>
                <span className="text-stone-500">{formatPlace(b)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {text.trim().length >= 2 && search.isSuccess && search.data.length === 0 && (
        <p className="mt-1 text-xs text-stone-500">No breweries match.</p>
      )}
    </div>
  )
}
