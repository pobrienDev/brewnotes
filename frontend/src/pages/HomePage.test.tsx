import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HomePage } from './HomePage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function fakeFetch(health: Response, me: Response) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    return url.includes('/health/live') ? health.clone() : me.clone()
  })
}

describe('HomePage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the API status and a sign-in link for visitors', async () => {
    vi.stubGlobal(
      'fetch',
      fakeFetch(
        new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } }),
        new Response(JSON.stringify({ title: 'Unauthorized', status: 401 }), { status: 401, headers: { 'content-type': 'application/problem+json' } }),
      ),
    )
    renderPage()
    await waitFor(() => expect(screen.getByTestId('api-status')).toHaveTextContent('ok'))
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument()
  })

  it('reports an unreachable API', async () => {
    vi.stubGlobal(
      'fetch',
      fakeFetch(
        new Response(JSON.stringify({ title: 'Service Unavailable', status: 503 }), { status: 503, headers: { 'content-type': 'application/problem+json' } }),
        new Response(JSON.stringify({ title: 'Unauthorized', status: 401 }), { status: 401, headers: { 'content-type': 'application/problem+json' } }),
      ),
    )
    renderPage()
    await waitFor(() => expect(screen.getByTestId('api-status')).toHaveTextContent('unreachable'))
  })
})
