import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useMe } from '../hooks/useMe'
import { useStyleRecommendations } from '../hooks/useRecommendations'
import {
  type AnswerKey,
  type Answers,
  QUESTIONS,
  type StyleSuggestion,
  answerLabel,
  closeness,
  describeDifferences,
  describeReason,
  hasAnswers,
  parseAnswers,
  trimRating,
} from '../lib/recommendations'
import { formatGravity, srmColor, trim } from '../lib/units'

const storageKey = (userId: string) => `brewnotes.answers.${userId}`

function loadStoredAnswers(userId: string): Answers {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    return raw ? parseAnswers(JSON.parse(raw) as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

function storeAnswers(userId: string, answers: Answers) {
  try {
    if (hasAnswers(answers)) localStorage.setItem(storageKey(userId), JSON.stringify(answers))
    else localStorage.removeItem(storageKey(userId))
  } catch {
    // Storage is a convenience only; the answers live in the URL.
  }
}

/** Suggestions from the user's own tastings (plan Phase 4), with the cold-start questions. */
export function ForYouPage() {
  const me = useMe()
  const userId = me.data?.id ?? ''
  const [params, setParams] = useSearchParams()
  const answers = parseAnswers(params)
  const answered = hasAnswers(answers)

  // Remembered answers fill the URL once, when it carries none.
  useEffect(() => {
    if (!userId || answered) return
    const stored = loadStoredAnswers(userId)
    if (hasAnswers(stored)) {
      const next = new URLSearchParams()
      for (const [key, value] of Object.entries(stored)) next.set(key, value)
      setParams(next, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per user
  }, [userId])

  const setAnswer = (key: AnswerKey, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    const updated = parseAnswers(next)
    if (userId) storeAnswers(userId, updated)
    setParams(next, { replace: true })
  }
  const clearAnswers = () => {
    if (userId) storeAnswers(userId, {})
    setParams(new URLSearchParams(), { replace: true })
  }

  const result = useStyleRecommendations(answers)
  const data = result.data
  const showQuestions = !data || data.cold_start || answered || data.suggestions.length === 0

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">For you</h1>
        <p className="max-w-prose text-sm text-stone-600">
          Styles you have not tried whose vital statistics sit closest to the ones you rate well. Only your own
          tastings count: beers with a style, and batches brewed to a target style.
        </p>
      </header>

      {result.isPending && <p className="text-stone-500">Loading…</p>}
      {result.isError && <p role="alert" className="text-red-800">{(result.error as Error).message}</p>}
      {data && result.isFetching && <p className="text-sm text-stone-500" aria-live="polite">Updating…</p>}

      {data && (
        <>
          {data.cold_start && (
            <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="cold-start">
              {data.tastings_with_style === 0 ? 'No tastings tied to a style yet' : `${data.tastings_with_style} of the ${data.min_tastings} tastings needed`}
              . Answer three quick questions and the suggestions start from those; they switch to your ratings once
              you have logged {data.min_tastings} tastings of styled beers or batches.
            </p>
          )}

          {showQuestions && (
            <fieldset className="space-y-3 rounded border border-stone-200 bg-white p-4">
              <legend className="px-1 font-semibold">What do you like?</legend>
              {QUESTIONS.map((question) => (
                <fieldset key={question.key} className="space-y-1">
                  <legend className="text-sm font-medium">{question.label}</legend>
                  <div className="flex flex-wrap gap-2">
                    {question.options.map(([value, label]) => {
                      const checked = answers[question.key] === value
                      return (
                        <label
                          key={value}
                          className={`cursor-pointer rounded border px-3 py-1 text-sm ${checked ? 'border-amber-600 bg-amber-100' : 'border-stone-300 hover:bg-stone-100'}`}
                        >
                          <input
                            type="radio"
                            name={question.key}
                            value={value}
                            className="sr-only"
                            checked={checked}
                            onChange={() => setAnswer(question.key, value)}
                          />
                          {label}
                        </label>
                      )
                    })}
                  </div>
                </fieldset>
              ))}
              {answered && (
                <p className="text-sm text-stone-600">
                  Using your answers:{' '}
                  {(Object.entries(answers) as [AnswerKey, string][]).map(([key, value]) => answerLabel(key, value).toLowerCase()).join(', ')}.{' '}
                  <button type="button" className="text-amber-800 underline" onClick={clearAnswers}>
                    Clear answers
                  </button>
                </p>
              )}
            </fieldset>
          )}

          <section className="space-y-3">
            <h2 className="text-xl font-semibold">Styles to try</h2>
            {data.suggestions.length === 0 ? (
              <p className="text-stone-600" data-testid="no-suggestions">
                {data.styles.length > 0 && !answered
                  ? 'Nothing stands out yet: suggestions follow styles you rate 3.5 or higher. Answer the questions above to start from those instead.'
                  : 'Answer the questions above, or rate a few beers that carry a style.'}
              </p>
            ) : (
              <ol className="grid gap-3 md:grid-cols-2" data-testid="suggestions">
                {data.suggestions.map((suggestion, index) => (
                  <SuggestionCard key={suggestion.style.slug} suggestion={suggestion} rank={index + 1} />
                ))}
              </ol>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold">Your taste so far</h2>
            {data.styles.length === 0 ? (
              <p className="text-stone-600">
                Nothing tied to a style yet. Give a <Link to="/beers" className="text-amber-700 hover:underline">beer</Link> a style, or brew a{' '}
                <Link to="/recipes" className="text-amber-700 hover:underline">recipe</Link> with a target style, and rate it.
              </p>
            ) : (
              <div className="grid gap-6 md:grid-cols-[2fr_1fr]">
                <table className="w-full text-sm" data-testid="rated-styles">
                  <caption className="sr-only">Average rating per style</caption>
                  <thead>
                    <tr className="text-left text-xs uppercase text-stone-500">
                      <th className="py-1 pr-3 font-medium">Style</th>
                      <th className="py-1 pr-3 font-medium">Tastings</th>
                      <th className="py-1 font-medium">Average</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.styles.map((s) => (
                      <tr key={s.slug} className="border-t border-stone-200">
                        <td className="py-1 pr-3">
                          <Link to={`/styles/${s.slug}`} className="text-amber-800 hover:underline">{s.display_name}</Link>
                          <span className="ml-2 text-xs text-stone-500">{s.category_name}</span>
                        </td>
                        <td className="py-1 pr-3">{s.count}</td>
                        <td className="py-1">{trimRating(s.mean)} / 5</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div>
                  <h3 className="text-sm font-medium">By family</h3>
                  <ul className="mt-1 divide-y divide-stone-200 text-sm" data-testid="rated-families">
                    {data.families.map((f) => (
                      <li key={f.category_code} className="flex justify-between gap-2 py-1">
                        <span>
                          <Link to={`/styles?category=${f.category_code}`} className="text-amber-800 hover:underline">
                            {f.category_code}. {f.category_name}
                          </Link>
                          <span className="ml-1 text-xs text-stone-500">({f.count})</span>
                        </span>
                        <span>{trimRating(f.mean)} / 5</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </section>
  )
}

const RANGE_LABELS: Record<string, string> = { og: 'OG', fg: 'FG', abv: 'ABV', ibu: 'IBU', srm: 'SRM' }

function rangeText(suggestion: StyleSuggestion, metric: 'og' | 'fg' | 'abv' | 'ibu' | 'srm'): string | null {
  const ranges = suggestion.style.ranges.filter((r) => r.metric === metric)
  if (ranges.length === 0) return null
  const fmt = (v: number) => (metric === 'og' || metric === 'fg' ? formatGravity(v) : metric === 'abv' ? `${trim(v, 1)}%` : trim(v, 1))
  return ranges.map((r) => `${fmt(r.min)}–${fmt(r.max)}`).join(' / ')
}

function SuggestionCard({ suggestion, rank }: { suggestion: StyleSuggestion; rank: number }) {
  const { style, because, differences } = suggestion
  const srm = style.ranges.filter((r) => r.metric === 'srm')
  const first = because[0]
  const rest = because.slice(1)
  return (
    <li className="rounded border border-stone-200 bg-white p-4" data-testid="suggestion">
      <div className="flex items-start gap-3">
        {srm.length > 0 && (
          <span
            aria-hidden="true"
            className="mt-1 inline-block h-8 w-8 shrink-0 rounded-full border border-stone-300"
            style={{ background: `linear-gradient(135deg, ${srmColor(srm[0].min)}, ${srmColor(srm[srm.length - 1].max)})` }}
          />
        )}
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">
            <span className="mr-2 text-stone-400">{rank}.</span>
            <Link to={`/styles/${style.slug}`} className="text-amber-800 hover:underline">{style.display_name}</Link>
          </h3>
          <p className="text-xs text-stone-500">{style.category_code}. {style.category_name}</p>
        </div>
        {first && (
          <span className="shrink-0 rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-700" title="How close its statistics are to the reason's">
            {closeness(first.distance)}
          </span>
        )}
      </div>
      {first && (
        <p className="mt-2 text-sm text-stone-800">
          Because {describeReason(first)}
          {first.kind === 'style' ? <>: {describeDifferences(differences)}.</> : '.'}
          {rest.length > 0 && <span className="text-stone-600"> Also because {rest.map(describeReason).join(' and ')}.</span>}
        </p>
      )}
      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-600">
        {(['abv', 'ibu', 'srm', 'og', 'fg'] as const).map((metric) => {
          const text = rangeText(suggestion, metric)
          return text === null ? null : (
            <div key={metric} className="flex gap-1">
              <dt className="font-medium">{RANGE_LABELS[metric]}</dt>
              <dd>{text}</dd>
            </div>
          )
        })}
      </dl>
    </li>
  )
}
