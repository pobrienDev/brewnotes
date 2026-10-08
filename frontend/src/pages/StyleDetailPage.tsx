import { Link, useNavigate, useParams } from 'react-router'

import { useAllStyles, useStyle } from '../hooks/useStyles'
import { formatGravity, srmColor, trim } from '../lib/units'

const LABELS: Record<string, string> = { og: 'Original gravity', fg: 'Final gravity', abv: 'ABV', ibu: 'IBU', srm: 'SRM' }
const fmt = (metric: string, v: number) => (metric === 'og' || metric === 'fg' ? formatGravity(v) : metric === 'abv' ? `${trim(v, 1)}%` : trim(v, 1))

export function StyleDetailPage() {
  const { slug } = useParams()
  const style = useStyle(slug)
  const all = useAllStyles()
  const navigate = useNavigate()
  if (style.isPending) return <p className="text-stone-500">Loading…</p>
  if (style.isError || !style.data) {
    return (
      <p role="alert" className="text-red-800">
        {(style.error as Error | undefined)?.message ?? 'No such style'}. <Link to="/styles" className="underline">All styles</Link>
      </p>
    )
  }
  const s = style.data
  const srm = s.ranges.filter((r) => r.metric === 'srm')
  return (
    <article className="max-w-3xl space-y-5">
      <nav className="text-sm text-stone-500">
        <Link to="/styles" className="hover:underline">Styles</Link> · {s.category_code}. {s.category_name}
        {s.parent && (
          <>
            {' · '}
            <Link to={`/styles/${s.parent.slug}`} className="hover:underline">{s.parent.display_name}</Link>
          </>
        )}
      </nav>
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">{s.display_name}</h1>
        {srm.length > 0 && (
          <span className="flex items-center gap-1 text-sm text-stone-600">
            {srm.map((r) => (
              <span key={`${r.min}-${r.max}`} className="flex items-center gap-1">
                <span aria-hidden="true" className="inline-block h-5 w-5 rounded border border-stone-300" style={{ backgroundColor: srmColor(r.min) }} />
                <span aria-hidden="true" className="inline-block h-5 w-5 rounded border border-stone-300" style={{ backgroundColor: srmColor(r.max) }} />
                {r.label && <span>{r.label}</span>}
              </span>
            ))}
          </span>
        )}
      </header>
      <p className="text-stone-800">{s.summary}</p>
      {s.ranges.length > 0 ? (
        <table className="w-full max-w-xl text-sm">
          <caption className="sr-only">Vital statistics</caption>
          <tbody>
            {(['og', 'fg', 'abv', 'ibu', 'srm'] as const).map((metric) => {
              const ranges = s.ranges.filter((r) => r.metric === metric)
              if (ranges.length === 0) return null
              return (
                <tr key={metric} className="border-t border-stone-200">
                  <th scope="row" className="py-1 pr-3 text-left font-medium">{LABELS[metric]}</th>
                  <td className="py-1">
                    {ranges.map((r) => (
                      <span key={`${r.min}-${r.max}`} className="mr-3">
                        {fmt(metric, r.min)} – {fmt(metric, r.max)}{r.label && <span className="text-stone-500"> ({r.label})</span>}
                      </span>
                    ))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-stone-600">This style's statistics vary with the base beer, so it is not matched by the calculator.</p>
      )}
      {s.variants.length > 0 && (
        <section>
          <h2 className="font-semibold">Variants</h2>
          <ul className="list-disc pl-5 text-sm">
            {s.variants.map((v) => (
              <li key={v.slug}><Link to={`/styles/${v.slug}`} className="text-amber-800 hover:underline">{v.name}</Link></li>
            ))}
          </ul>
        </section>
      )}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label>
          Compare with
          <select className="ml-2 rounded border border-stone-300 px-2 py-1" defaultValue="" onChange={(e) => e.target.value && navigate(`/styles/compare?a=${s.slug}&b=${e.target.value}`)}>
            <option value="">choose a style…</option>
            {all.data?.filter((o) => o.slug !== s.slug).map((o) => (
              <option key={o.slug} value={o.slug}>{o.display_name}</option>
            ))}
          </select>
        </label>
        <Link to={`/recipes/new?target=${s.slug}`} className="text-amber-800 hover:underline">Design a recipe for this style</Link>
        {s.source_url && (
          <a href={s.source_url} target="_blank" rel="noreferrer" className="text-stone-600 hover:underline">
            {s.guideline} {s.guideline_version} guideline page
          </a>
        )}
      </div>
    </article>
  )
}
