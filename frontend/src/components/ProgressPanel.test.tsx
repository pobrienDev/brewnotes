import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ProgressPanel } from './ProgressPanel'

describe('ProgressPanel', () => {
  it('prints every figure with its source', () => {
    render(
      <ProgressPanel
        fermentation={{
          og: 1.058,
          og_source: 'measured',
          current_sg: 1.02,
          current_sg_source: 'reading',
          apparent_attenuation_pct: 65.5,
          abv: 4.99,
          expected_fg: 1.014,
          expected_attenuation_pct: 75.9,
          readings_count: 12,
          latest_reading_at: '2026-09-10T18:00:00Z',
        }}
      />,
    )
    expect(screen.getByText('1.058')).toBeInTheDocument()
    expect(screen.getByText('(measured)')).toBeInTheDocument()
    expect(screen.getByText('1.020')).toBeInTheDocument()
    expect(screen.getByText('(latest reading)')).toBeInTheDocument()
    expect(screen.getByText('65.5%')).toBeInTheDocument()
    expect(screen.getByText('(expected 75.9%)')).toBeInTheDocument()
    expect(screen.getByText('4.99%')).toBeInTheDocument()
    expect(screen.getByTestId('progress-pct')).toHaveTextContent('86%')
  })
  it('copes with a batch that has no readings yet', () => {
    render(
      <ProgressPanel
        fermentation={{
          og: 1.055,
          og_source: 'estimated',
          current_sg: null,
          current_sg_source: null,
          apparent_attenuation_pct: null,
          abv: null,
          expected_fg: 1.014,
          expected_attenuation_pct: 75,
          readings_count: 0,
          latest_reading_at: null,
        }}
      />,
    )
    expect(screen.getAllByText('(from the recipe)')).toHaveLength(2) // OG and expected FG
    expect(screen.getByText('(no readings yet)')).toBeInTheDocument()
    expect(screen.queryByTestId('progress-pct')).not.toBeInTheDocument()
  })
})
