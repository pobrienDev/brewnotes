import type { components } from '../api/schema'
import { formatGravity, trim } from '../lib/units'

type MetricMatch = components['schemas']['MetricMatchOut']
type Range = components['schemas']['RangeOut']

const LABELS: Record<string, string> = { og: 'OG', fg: 'FG', abv: 'ABV', ibu: 'IBU', srm: 'SRM' }

function fmt(metric: string, value: number): string {
  if (metric === 'og' || metric === 'fg') return formatGravity(value)
  if (metric === 'abv') return `${trim(value, 1)}%`
  return trim(value, 1)
}

/**
 * One metric's style range(s) with the recipe's value marked. The value and a text status
 * ("low"/"high") are always printed, so the bar is never the only signal.
 */
export function RangeBar({ match }: { match: MetricMatch }) {
  const lows = match.ranges.map((r) => r.min)
  const highs = match.ranges.map((r) => r.max)
  const min = Math.min(...lows, match.value)
  const max = Math.max(...highs, match.value)
  const pad = (max - min || 1) * 0.1
  const lo = min - pad
  const hi = max + pad
  const pct = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`
  const statusText = match.status === 'in' ? 'in range' : match.status
  return (
    <div className="grid grid-cols-[3rem_1fr_7rem] items-center gap-2 text-sm">
      <span className="font-medium">{LABELS[match.metric] ?? match.metric}</span>
      <div className="relative h-4 rounded bg-stone-200" aria-hidden="true">
        {match.ranges.map((r: Range, i) => (
          <div
            key={`${r.min}-${r.max}-${i}`}
            className="absolute top-0 h-4 rounded bg-amber-300"
            style={{ left: pct(r.min), width: `calc(${pct(r.max)} - ${pct(r.min)})` }}
            title={r.label ?? undefined}
          />
        ))}
        <div
          className={`absolute top-[-2px] h-5 w-1 rounded ${match.status === 'in' ? 'bg-stone-900' : 'bg-red-700'}`}
          style={{ left: `calc(${pct(match.value)} - 2px)` }}
        />
      </div>
      <span className={match.status === 'in' ? 'text-stone-700' : 'text-red-800'}>
        {fmt(match.metric, match.value)} <span className="text-xs">({statusText})</span>
      </span>
      <span className="sr-only">
        Ranges: {match.ranges.map((r) => `${fmt(match.metric, r.min)} to ${fmt(match.metric, r.max)}${r.label ? ` (${r.label})` : ''}`).join(', ')}
      </span>
    </div>
  )
}
