import type { components } from '../api/schema'

export type StyleRecommendations = components['schemas']['StyleRecommendations']
export type StyleSuggestion = components['schemas']['StyleSuggestion']
export type Reason = components['schemas']['Reason']
export type Difference = components['schemas']['Difference']

export type Strength = 'session' | 'standard' | 'strong'
export type Bitterness = 'soft' | 'balanced' | 'bitter'
export type Color = 'pale' | 'amber' | 'dark'

export interface Answers {
  strength?: Strength
  bitterness?: Bitterness
  color?: Color
}

export type AnswerKey = keyof Answers

/** The cold-start questions, in the order they are asked. Values match the API's. */
export const QUESTIONS: ReadonlyArray<{
  key: AnswerKey
  label: string
  options: ReadonlyArray<readonly [string, string]>
}> = [
  {
    key: 'strength',
    label: 'How strong do you like a beer?',
    options: [
      ['session', 'Session, under 4.5%'],
      ['standard', 'Standard, 4.5 to 6.5%'],
      ['strong', 'Strong, over 6.5%'],
    ],
  },
  {
    key: 'bitterness',
    label: 'How bitter?',
    options: [
      ['soft', 'Soft, hardly any'],
      ['balanced', 'Balanced'],
      ['bitter', 'Bitter, hop-forward'],
    ],
  },
  {
    key: 'color',
    label: 'How dark?',
    options: [
      ['pale', 'Pale, straw to gold'],
      ['amber', 'Amber to brown'],
      ['dark', 'Dark, brown to black'],
    ],
  },
]

const ALLOWED: Record<AnswerKey, ReadonlySet<string>> = {
  strength: new Set(QUESTIONS[0].options.map(([value]) => value)),
  bitterness: new Set(QUESTIONS[1].options.map(([value]) => value)),
  color: new Set(QUESTIONS[2].options.map(([value]) => value)),
}

/** Answers from a query string or stored object; anything unrecognised is dropped. */
export function parseAnswers(source: URLSearchParams | Record<string, unknown> | null | undefined): Answers {
  const answers: Answers = {}
  if (!source) return answers
  const read = (key: AnswerKey): unknown => (source instanceof URLSearchParams ? source.get(key) : source[key])
  const strength = read('strength')
  const bitterness = read('bitterness')
  const color = read('color')
  if (typeof strength === 'string' && ALLOWED.strength.has(strength)) answers.strength = strength as Strength
  if (typeof bitterness === 'string' && ALLOWED.bitterness.has(bitterness)) answers.bitterness = bitterness as Bitterness
  if (typeof color === 'string' && ALLOWED.color.has(color)) answers.color = color as Color
  return answers
}

export const hasAnswers = (answers: Answers) => Boolean(answers.strength || answers.bitterness || answers.color)

export const answerLabel = (key: AnswerKey, value: string): string =>
  QUESTIONS.find((q) => q.key === key)?.options.find(([v]) => v === value)?.[1] ?? value

const WORDS: Record<string, Record<'higher' | 'lower', string>> = {
  abv: { higher: 'stronger', lower: 'lighter' },
  fg: { higher: 'fuller', lower: 'drier' },
  ibu: { higher: 'more bitter', lower: 'less bitter' },
  srm: { higher: 'darker', lower: 'paler' },
}
const WORD_ORDER = ['abv', 'ibu', 'srm', 'fg']

/**
 * "stronger, more bitter and darker": how a suggestion differs from the style it is
 * suggested for. OG is left out because ABV already says how strong the beer is.
 */
export function describeDifferences(differences: readonly Difference[]): string {
  const words = WORD_ORDER.flatMap((metric) => {
    const found = differences.find((d) => d.metric === metric)
    return found ? [WORDS[metric][found.direction]] : []
  })
  if (words.length === 0) return 'much the same numbers'
  if (words.length === 1) return words[0]
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

/** "you rated 21A American IPA 4.5 on average (4 tastings)" or "of your answers". */
export function describeReason(reason: Reason): string {
  if (reason.kind === 'answers' || !reason.style) return 'of your answers'
  const rating = reason.rating === null ? '' : ` ${trimRating(reason.rating)}`
  const count = reason.count === 1 ? 'once' : `on average (${reason.count} tastings)`
  return `you rated ${reason.style.display_name}${rating} ${count}`
}

export const trimRating = (rating: number) => Number(rating.toFixed(2)).toString()

/** A word for the distance in vital statistics (0 is identical; see the API's Reason). */
export function closeness(distance: number): 'near twin' | 'close' | 'further afield' {
  if (distance < 0.06) return 'near twin'
  if (distance < 0.14) return 'close'
  return 'further afield'
}
