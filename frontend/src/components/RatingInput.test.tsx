import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RatingDisplay, RatingInput } from './RatingInput'

describe('RatingInput', () => {
  it('offers ten labelled half-step options and reports the choice', async () => {
    const onChange = vi.fn()
    render(<RatingInput value={null} onChange={onChange} />)
    expect(screen.getAllByRole('radio')).toHaveLength(10)
    await userEvent.click(screen.getByRole('radio', { name: '3.5 out of 5' }))
    expect(onChange).toHaveBeenCalledWith(3.5)
  })
  it('shows the current value as text', () => {
    render(<RatingInput value={4} onChange={() => {}} />)
    expect(screen.getByText('4 / 5')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '4 out of 5' })).toBeChecked()
  })
})

describe('RatingDisplay', () => {
  it('prints the number next to the stars', () => {
    render(<RatingDisplay rating={2.5} />)
    expect(screen.getByText('2.5 / 5')).toBeInTheDocument()
  })
})
