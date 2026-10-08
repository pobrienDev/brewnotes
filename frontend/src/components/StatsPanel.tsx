import type { components } from '../api/schema'
import { formatGravity, srmColor, trim } from '../lib/units'

type Stats = components['schemas']['RecipeStatsOut']

export function StatsPanel({ stats, notes, error }: { stats?: Stats; notes?: string[]; error?: string }) {
  return (
    <section
      aria-labelledby="stats"
      className="sticky bottom-0 z-10 rounded border border-stone-200 bg-white p-3 shadow-sm lg:static lg:shadow-none"
    >
      <h2 id="stats" className="sr-only">
        Statistics
      </h2>
      {error && (
        <p role="alert" className="mb-2 text-sm text-red-800">
          {error}
        </p>
      )}
      <dl className="grid grid-cols-5 gap-2 text-center lg:grid-cols-1 lg:text-left">
        <Stat label="OG" value={stats ? formatGravity(stats.og) : '–'} />
        <Stat label="FG" value={stats ? formatGravity(stats.fg) : '–'} />
        <Stat label="ABV" value={stats ? `${trim(stats.abv, 1)}%` : '–'} />
        <Stat label="IBU" value={stats ? trim(stats.ibu, 0) : '–'} />
        <div>
          <dt className="text-xs uppercase text-stone-500">SRM</dt>
          <dd className="flex items-center justify-center gap-2 font-semibold lg:justify-start">
            {stats && (
              <span
                aria-hidden="true"
                className="inline-block h-5 w-5 rounded border border-stone-300"
                style={{ backgroundColor: srmColor(stats.srm) }}
              />
            )}
            {stats ? trim(stats.srm, 1) : '–'}
          </dd>
        </div>
      </dl>
      {notes && notes.length > 0 && (
        <ul className="mt-2 hidden list-disc pl-5 text-xs text-stone-600 lg:block">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase text-stone-500">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  )
}
