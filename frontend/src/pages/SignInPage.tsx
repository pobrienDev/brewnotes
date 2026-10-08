import { Link, Navigate, useSearchParams } from 'react-router'

import { useMe } from '../hooks/useMe'
import { useProviders } from '../hooks/useProviders'
import { PROVIDER_LABELS, loginUrl } from '../lib/auth'

const ERRORS: Record<string, string> = {
  state: 'That sign-in link had expired or was not started here. Please try again.',
  cancelled: 'Sign-in was cancelled.',
  provider: 'The sign-in provider did not complete the request. Please try again.',
}

export function SignInPage() {
  const me = useMe()
  const providers = useProviders()
  const [params] = useSearchParams()
  const next = params.get('next') ?? '/recipes'
  const error = params.get('error')

  if (me.data) return <Navigate to={next} replace />

  return (
    <section className="mx-auto max-w-md space-y-6">
      <h1 className="text-2xl font-bold">Sign in</h1>
      <p className="text-stone-700">
        The calculator and style browser work without an account. Saving recipes needs one.
        BrewNotes stores no password and no email address.
      </p>
      {error && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {ERRORS[error] ?? 'Sign-in failed.'}
        </p>
      )}
      <div className="flex flex-col gap-3">
        {providers.data?.map((provider) => (
          <a
            key={provider}
            href={loginUrl(provider, next)}
            className="rounded border border-stone-300 bg-white px-4 py-2 text-center font-medium hover:bg-stone-100"
          >
            Continue with {PROVIDER_LABELS[provider] ?? provider}
          </a>
        ))}
        {providers.data?.length === 0 && (
          <p className="text-sm text-stone-600">No sign-in provider is configured on this server.</p>
        )}
      </div>
      <p className="text-sm text-stone-500">
        <Link to="/privacy" className="hover:underline">
          What BrewNotes stores
        </Link>
      </p>
    </section>
  )
}
