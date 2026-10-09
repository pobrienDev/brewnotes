import { Link } from 'react-router'

import { useApiHealth } from '../hooks/useApiHealth'
import { useMe } from '../hooks/useMe'

export function HomePage() {
  const health = useApiHealth()
  const me = useMe()
  const apiStatus = health.isPending ? 'checking…' : health.isError ? 'unreachable' : health.data.status
  return (
    <section className="space-y-6">
      <div className="space-y-3">
        <h1 className="text-3xl font-bold">Design it. Brew it. Taste it.</h1>
        <p className="max-w-prose text-stone-700">
          Build a recipe and watch gravity, alcohol, bitterness and colour update as you type, see which
          BJCP styles it fits and what is out of range, and scale it to any batch size. Then brew it:
          log gravity and temperature readings, watch the fermentation chart, and rate the result next
          to the commercial beers you have tried, find breweries near you on the map, and get styles
          to try next from your own ratings. No account needed for the calculator, styles or the map;
          sign in with GitHub or Google to save recipes and keep a brewing log.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link to="/recipes/new" className="rounded bg-amber-600 px-4 py-2 text-white hover:bg-amber-700">Open the calculator</Link>
        <Link to="/styles" className="rounded border border-stone-300 px-4 py-2 hover:bg-stone-100">Browse styles</Link>
        <Link to="/breweries" className="rounded border border-stone-300 px-4 py-2 hover:bg-stone-100">Find breweries</Link>
        {me.data ? (
          <>
            <Link to="/recipes" className="rounded border border-stone-300 px-4 py-2 hover:bg-stone-100">My recipes</Link>
            <Link to="/batches" className="rounded border border-stone-300 px-4 py-2 hover:bg-stone-100">Batches</Link>
            <Link to="/for-you" className="rounded border border-stone-300 px-4 py-2 hover:bg-stone-100">Styles for you</Link>
          </>
        ) : (
          <Link to="/sign-in" className="rounded border border-stone-300 px-4 py-2 hover:bg-stone-100">Sign in</Link>
        )}
      </div>
      <p className="text-sm text-stone-500">
        API status: <span data-testid="api-status">{apiStatus}</span>
      </p>
    </section>
  )
}
