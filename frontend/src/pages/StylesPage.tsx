import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { type StyleSummary, useAllStyles } from '../hooks/useStyles'
import { formatGravity, trim } from '../lib/units'

function rangeText(style: StyleSummary, metric: string): string {
  const ranges = style.ranges.filter((r) => r.metric === metric)
  if (ranges.length === 0) return '–'
  const fmt = (v: number) => (metric === 'og' || metric === 'fg' ? formatGravity(v) : trim(v, 1))
  return ranges.map((r) => `${fmt(r.min)}–${fmt(r.max)}${r.label ? ` ${r.label}` : ''}`).join(', ')
}

export function StylesPage() {
  const styles = useAllStyles()
  const [params, setParams] = useSearchParams()
  const search = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const [compare, setCompare] = useState<string[]>([])

  const categories = useMemo(() => {
    const seen = new Map<string, string>()
    for (const s of styles.data ?? []) seen.set(s.category_code, s.category_name)
    return [...seen.entries()]
  }, [styles.data])

  const visible = (styles.data ?? []).filter((s) => {
    if (category && s.category_code !== category) return false
    if (!search) return true
    const q = search.toLowerCase()
    return s.display_name.toLowerCase().includes(q) || (s.code ?? '').toLowerCase().includes(q)
  })

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const toggleCompare = (slug: string) =>
    setCompare((c) => (c.includes(slug) ? c.filter((x) => x !== slug) : [...c, slug].slice(-2)))

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end gap-3">
        <h1 className="text-2xl font-bold">BJCP 2021 styles</h1>
        <span className="flex-1" />
        <label className="text-sm">
          Search
          <input className="ml-2 rounded border border-stone-300 px-2 py-1" value={search} onChange={(e) => update('q', e.target.value)} placeholder="name or code" />
        </label>
        <label className="text-sm">
          Category
          <select className="ml-2 rounded border border-stone-300 px-2 py-1" value={category} onChange={(e) => update('category', e.target.value)}>
            <option value="">All</option>
            {categories.map(([code, name]) => (
              <option key={code} value={code}>
                {code}. {name}
              </option>
            ))}
          </select>
        </label>
        {compare.length === 2 && (
          <Link to={`/styles/compare?a=${compare[0]}&b=${compare[1]}`} className="rounded bg-amber-600 px-3 py-1 text-sm text-white">
            Compare selected
          </Link>
        )}
      </header>
      {styles.isPending && <p className="text-stone-500">Loading…</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="py-1 pr-2"><span className="sr-only">Compare</span></th><th className="py-1 pr-3">Style</th><th className="py-1 pr-3">OG</th><th className="py-1 pr-3">FG</th><th className="py-1 pr-3">ABV %</th><th className="py-1 pr-3">IBU</th><th className="py-1">SRM</th></tr>
          </thead>
          <tbody>
            {visible.map((s) => (
              <tr key={s.slug} className={`border-t border-stone-200 ${s.parent_slug ? 'text-stone-700' : ''}`}>
                <td className="py-1 pr-2">
                  <input type="checkbox" aria-label={`Compare ${s.display_name}`} checked={compare.includes(s.slug)} onChange={() => toggleCompare(s.slug)} />
                </td>
                <td className="py-1 pr-3">
                  <Link to={`/styles/${s.slug}`} className={`hover:underline ${s.parent_slug ? 'pl-4' : 'font-medium'}`}>
                    {s.display_name}
                  </Link>
                </td>
                <td className="py-1 pr-3">{rangeText(s, 'og')}</td>
                <td className="py-1 pr-3">{rangeText(s, 'fg')}</td>
                <td className="py-1 pr-3">{rangeText(s, 'abv')}</td>
                <td className="py-1 pr-3">{rangeText(s, 'ibu')}</td>
                <td className="py-1">{rangeText(s, 'srm')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {styles.isSuccess && visible.length === 0 && <p className="text-stone-600">No styles match.</p>}
    </section>
  )
}
