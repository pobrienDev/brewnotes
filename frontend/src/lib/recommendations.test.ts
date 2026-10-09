import { describe, expect, it } from 'vitest'

import {
  QUESTIONS,
  answerLabel,
  closeness,
  describeDifferences,
  describeReason,
  hasAnswers,
  parseAnswers,
  trimRating,
} from './recommendations'

describe('parseAnswers', () => {
  it('keeps only known values from a query string', () => {
    const params = new URLSearchParams('strength=strong&bitterness=sweet&color=dark&limit=3')
    expect(parseAnswers(params)).toEqual({ strength: 'strong', color: 'dark' })
  })
  it('reads a stored object and ignores junk', () => {
    expect(parseAnswers({ strength: 'session', color: 42, extra: true })).toEqual({ strength: 'session' })
    expect(parseAnswers(null)).toEqual({})
    expect(hasAnswers({})).toBe(false)
    expect(hasAnswers({ bitterness: 'soft' })).toBe(true)
  })
  it('labels every option', () => {
    for (const question of QUESTIONS) {
      for (const [value, label] of question.options) expect(answerLabel(question.key, value)).toBe(label)
    }
    expect(answerLabel('color', 'unknown')).toBe('unknown')
  })
})

describe('describeDifferences', () => {
  it('words the metrics in a fixed order and skips OG', () => {
    expect(
      describeDifferences([
        { metric: 'og', direction: 'higher' },
        { metric: 'srm', direction: 'higher' },
        { metric: 'ibu', direction: 'lower' },
        { metric: 'abv', direction: 'higher' },
      ]),
    ).toBe('stronger, less bitter and darker')
    expect(describeDifferences([{ metric: 'fg', direction: 'lower' }])).toBe('drier')
    expect(describeDifferences([{ metric: 'srm', direction: 'lower' }, { metric: 'abv', direction: 'lower' }])).toBe('lighter and paler')
    expect(describeDifferences([])).toBe('much the same numbers')
    expect(describeDifferences([{ metric: 'og', direction: 'lower' }])).toBe('much the same numbers')
  })
})

describe('describeReason', () => {
  const style = { slug: 'american-ipa', display_name: '21A American IPA', category_code: '21', category_name: 'IPA' }
  it('names the rated style with its average and count', () => {
    expect(describeReason({ kind: 'style', style, rating: 4.5, count: 4, distance: 0.03 })).toBe(
      'you rated 21A American IPA 4.5 on average (4 tastings)',
    )
    expect(describeReason({ kind: 'style', style, rating: 4, count: 1, distance: 0.03 })).toBe('you rated 21A American IPA 4 once')
    expect(describeReason({ kind: 'style', style, rating: 4.333333, count: 3, distance: 0.03 })).toBe(
      'you rated 21A American IPA 4.33 on average (3 tastings)',
    )
  })
  it('points at the answers otherwise', () => {
    expect(describeReason({ kind: 'answers', style: null, rating: null, count: 0, distance: 0.1 })).toBe('of your answers')
  })
  it('trims ratings', () => {
    expect(trimRating(4.5)).toBe('4.5')
    expect(trimRating(4)).toBe('4')
  })
})

describe('closeness', () => {
  it('maps the distance to a word', () => {
    expect(closeness(0)).toBe('near twin')
    expect(closeness(0.059)).toBe('near twin')
    expect(closeness(0.1)).toBe('close')
    expect(closeness(0.3)).toBe('further afield')
  })
})
