import { type FermentationOut, attenuationProgressPct } from '../lib/batches'
import { formatDateTime } from '../lib/time'
import { formatGravity, trim } from '../lib/units'

const SOURCE: Record<string, string> = {
  measured: 'measured',
  estimated: 'from the recipe',
  reading: 'latest reading',
}

/** Where fermentation stands. Every figure is printed with where it came from. */
export function ProgressPanel({ fermentation: f }: { fermentation: FermentationOut }) {
  const progress = attenuationProgressPct(f)
  return (
    <section aria-labelledby="progress" className="rounded border border-stone-200 bg-white p-3">
      <h2 id="progress" className="mb-2 font-semibold">
        Fermentation
      </h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <Item label="OG" value={formatGravity(f.og)} source={SOURCE[f.og_source]} />
        <Item
          label="Current gravity"
          value={f.current_sg === null ? '–' : formatGravity(f.current_sg)}
          source={f.current_sg_source ? SOURCE[f.current_sg_source] : 'no readings yet'}
        />
        <Item label="Expected FG" value={formatGravity(f.expected_fg)} source="from the recipe" />
        <Item
          label="Apparent attenuation"
          value={f.apparent_attenuation_pct === null ? '–' : `${trim(f.apparent_attenuation_pct, 1)}%`}
          source={f.expected_attenuation_pct === null ? undefined : `expected ${trim(f.expected_attenuation_pct, 1)}%`}
        />
        <Item label="ABV so far" value={f.abv === null ? '–' : `${trim(f.abv, 2)}%`} />
        <Item
          label="Readings"
          value={String(f.readings_count)}
          source={f.latest_reading_at ? `latest ${formatDateTime(f.latest_reading_at)}` : undefined}
        />
      </dl>
      {progress !== null && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-stone-600">
            <span>Progress towards expected attenuation</span>
            <span data-testid="progress-pct">{trim(progress, 0)}%</span>
          </div>
          <div className="mt-1 h-2 rounded bg-stone-200" aria-hidden="true">
            <div className="h-2 rounded bg-amber-500" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
    </section>
  )
}

function Item({ label, value, source }: { label: string; value: string; source?: string }) {
  return (
    <div>
      <dt className="text-xs uppercase text-stone-500">{label}</dt>
      <dd className="font-semibold">
        {value}
        {source && <span className="ml-1 text-xs font-normal text-stone-500">({source})</span>}
      </dd>
    </div>
  )
}
