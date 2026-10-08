import { useId, useState } from 'react'

import { type CatalogItem, type CatalogKind, useCatalogSearch } from '../hooks/useCatalog'

/**
 * A text input with suggestions from the catalog. Typing keeps the free-text name; picking a
 * suggestion hands the item back so the row can copy its values and keep the reference.
 */
export function CatalogPicker({
  kind,
  value,
  onChange,
  onPick,
  label,
}: {
  kind: CatalogKind
  value: string
  onChange: (name: string) => void
  onPick: (item: CatalogItem) => void
  label: string
}) {
  const [open, setOpen] = useState(false)
  const search = useCatalogSearch(kind, value)
  const listId = useId()
  const suggestions = open && search.data ? search.data : []
  return (
    <div className="relative">
      <input
        aria-label={label}
        aria-autocomplete="list"
        aria-controls={listId}
        aria-expanded={suggestions.length > 0}
        className="w-full rounded border border-stone-300 px-2 py-1"
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        placeholder="Type to search…"
      />
      {suggestions.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded border border-stone-300 bg-white shadow"
        >
          {suggestions.map((item) => (
            <li key={item.id} role="option" aria-selected={false}>
              <button
                type="button"
                className="flex w-full justify-between px-2 py-1 text-left text-sm hover:bg-amber-50"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onPick(item)
                  setOpen(false)
                }}
              >
                <span>{item.name}</span>
                <span className="text-stone-500">{describe(item)}{item.custom ? ' · mine' : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function describe(item: CatalogItem): string {
  if ('ppg' in item) return `${item.ppg} PPG · ${item.color_lovibond} °L`
  if ('alpha_typical_pct' in item) return `${item.alpha_typical_pct}% AA`
  return `${item.lab} · ${item.attenuation_midpoint_pct}%`
}
