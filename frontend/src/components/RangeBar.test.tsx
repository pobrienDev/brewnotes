import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RangeBar } from './RangeBar'

describe('RangeBar', () => {
  it('prints the value and status as text, not colour alone', () => {
    render(
      <RangeBar
        match={{
          metric: 'ibu',
          value: 25,
          ranges: [{ min: 30, max: 50, label: null }],
          status: 'low',
          delta: -5,
          penalty: 0.25,
        }}
      />,
    )
    expect(screen.getByText(/25/)).toBeInTheDocument()
    expect(screen.getByText(/\(low\)/)).toBeInTheDocument()
    expect(screen.getByText(/Ranges: 30 to 50/)).toBeInTheDocument()
  })
})
