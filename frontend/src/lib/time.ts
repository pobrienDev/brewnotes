/** Local <input type="datetime-local"> values to and from the API's UTC timestamps. */

const pad = (n: number) => String(n).padStart(2, '0')

/** "YYYY-MM-DDTHH:mm" in the browser's time zone, what a datetime-local input wants. */
export function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** The input's local value as an ISO timestamp with offset (UTC "Z"); null when blank. */
export function fromLocalInputValue(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatDate(isoDate: string): string {
  // Calendar dates (brew day) have no time zone; parse the parts so the day never shifts.
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export const todayInputValue = () => toLocalInputValue(new Date()).slice(0, 10)
