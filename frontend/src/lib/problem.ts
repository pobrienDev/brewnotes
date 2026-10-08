import type { components } from '../api/schema'

export type Problem = components['schemas']['Problem']

/** A readable message from an RFC 9457 problem, including field errors when present. */
export function describeProblem(problem: Problem | undefined, fallback = 'Something went wrong'): string {
  if (!problem) return fallback
  const fields = (problem.errors ?? [])
    .map((e) => `${e.loc.filter((p) => p !== 'body').join('.')}: ${e.msg}`)
    .slice(0, 3)
  const head = problem.detail ?? problem.title ?? fallback
  return fields.length ? `${head} (${fields.join('; ')})` : head
}
