import { useApiHealth } from '../hooks/useApiHealth'

export function HomePage() {
  const health = useApiHealth()
  const apiStatus = health.isPending ? 'checking…' : health.isError ? 'unreachable' : health.data.status

  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold">Design it. Brew it. Taste it.</h1>
      <p className="max-w-prose text-stone-700">
        BrewNotes follows a beer from recipe to glass. The recipe designer arrives in Phase 1.
      </p>
      <p className="text-sm text-stone-500">
        API status: <span data-testid="api-status">{apiStatus}</span>
      </p>
    </section>
  )
}
