import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HomePage } from './HomePage'

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

describe('HomePage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the API status from the health endpoint', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ status: 'ok' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )
    renderWithQuery(<HomePage />)
    await waitFor(() => expect(screen.getByTestId('api-status')).toHaveTextContent('ok'))
  })

  it('reports an unreachable API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ title: 'Service Unavailable', status: 503 }), {
          status: 503,
          headers: { 'content-type': 'application/problem+json' },
        }),
      ),
    )
    renderWithQuery(<HomePage />)
    await waitFor(() =>
      expect(screen.getByTestId('api-status')).toHaveTextContent('unreachable'),
    )
  })
})
