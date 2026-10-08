import { Link, useSearchParams } from 'react-router'

import { useAllStyles, useStyle } from '../hooks/useStyles'
import { formatGravity, trim } from '../lib/units'

const METRICS = ['og', 'fg', 'abv', 'ibu', 'srm'] as const
const LABELS: Record<string, string> = { og: 'OG', fg: 'FG', abv: 'ABV %', ibu: 'IBU', srm: 'SRM' }
const fmt = (metric: string, v: number) => (metric === 'og' || metric === 'fg' ? formatGravity(v) : trim(v, 1))

export function StyleComparePage() {
  const [params, setParams] = useSearchParams()
  const a = useStyle(params.get('a') ?? undefined)
  const b = useStyle(params.get('b') ?? undefined)
  const all = useAllStyles()
  const set = (key: 'a' | 'b', slug: string) => {
    const next = new URLSearchParams(params)
    next.set(key, slug)
    setParams(next, { replace: true })
  }
  const picker = (key: 'a' | 'b') => (
    <select className="w-full rounded border border-stone-300 px-2 py-1" value={params.get(key) ?? ''} onChange={(e) => set(key, e.target.value)} aria-label={`Style ${key.toUpperCase()}`}>
      <option value="">choose…</option>
      {all.data?.map((s) => (
        <option key={s.slug} value={s.slug}>{s.display_name}</option>
      ))}
    </select>
  )
  return (
    <section className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold">Compare styles</h1>
      <table className="w-full text-sm">
        <thead>
          <tr><th className="w-24" /><th className="pb-2">{picker('a')}</th><th className="pb-2">{picker('b')}</th></tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => (
            <tr key={metric} className="border-t border-stone-200">
              <th scope="row" className="py-1 text-left">{LABELS[metric]}</th>
              {[a, b].map((q, i) => (
                <td key={i} className="py-1 pl-3">
                  {q.data
                    ? q.data.ranges.filter((r) => r.metric === metric).map((r) => (
                        <span key={`${r.min}-${r.max}`} className="mr-2">
                          {fmt(metric, r.min)}–{fmt(metric, r.max)}{r.label ? ` (${r.label})` : ''}
                        </span>
                      ))
                    : '–'}
                  {q.data && q.data.ranges.filter((r) => r.metric === metric).length === 0 && <span className="text-stone-500">varies</span>}
                </td>
              ))}
            </tr>
          ))}
          <tr className="border-t border-stone-200 align-top">
            <th scope="row" className="py-1 text-left">Summary</th>
            {[a, b].map((q, i) => (
              <td key={i} className="py-1 pl-3 text-stone-700">
                {q.data ? (
                  <>
                    {q.data.summary} <Link to={`/styles/${q.data.slug}`} className="text-amber-800 hover:underline">Details</Link>
                  </>
                ) : '–'}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </section>
  )
}
