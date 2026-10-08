import { Link } from 'react-router'

import type { components } from '../api/schema'
import { RangeBar } from './RangeBar'

type StyleMatch = components['schemas']['StyleMatchOut']

export function StyleMatchPanel({
  matches,
  targetSlug,
}: {
  matches: StyleMatch[]
  targetSlug: string | null
}) {
  const target = targetSlug ? matches.find((m) => m.slug === targetSlug) : undefined
  const others = matches.filter((m) => m !== target)
  if (matches.length === 0) return <p className="text-sm text-stone-500">Add ingredients to see style matches.</p>
  return (
    <section aria-labelledby="style-matches" className="space-y-4">
      <h2 id="style-matches" className="text-lg font-semibold">
        Style matches
      </h2>
      {target && <MatchCard match={target} heading="Target style" />}
      {others.map((m, i) => (
        <MatchCard key={m.slug} match={m} heading={i === 0 && !target ? 'Best match' : undefined} />
      ))}
    </section>
  )
}

function MatchCard({ match, heading }: { match: StyleMatch; heading?: string }) {
  return (
    <article className={`rounded border p-3 ${match.fits ? 'border-green-300 bg-green-50' : 'border-stone-200 bg-white'}`}>
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <div>
          {heading && <p className="text-xs uppercase tracking-wide text-stone-500">{heading}</p>}
          <Link to={`/styles/${match.slug}`} className="font-medium hover:underline">
            {match.display_name}
          </Link>
        </div>
        <span className={`text-sm ${match.fits ? 'text-green-800' : 'text-stone-600'}`}>
          {match.fits ? 'Fits' : `${match.metrics.filter((m) => m.status !== 'in').length} out of range`}
        </span>
      </header>
      <div className="space-y-1">
        {match.metrics.map((m) => (
          <RangeBar key={m.metric} match={m} />
        ))}
      </div>
    </article>
  )
}
