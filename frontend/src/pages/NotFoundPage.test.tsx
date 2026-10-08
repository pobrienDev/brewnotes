import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router'

import { NotFoundPage } from './NotFoundPage'

describe('NotFoundPage', () => {
  it('links back home', () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: /back to the start/i })).toHaveAttribute('href', '/')
  })
})
