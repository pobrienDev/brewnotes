/** Where the sign-in buttons send the browser. The backend restricts `next` to in-app paths. */
export function loginUrl(provider: string, next: string = window.location.pathname): string {
  const params = new URLSearchParams({ next })
  return `/api/v1/auth/login/${provider}?${params.toString()}`
}

export const linkUrl = (provider: string) => `/api/v1/auth/link/${provider}`

export const PROVIDER_LABELS: Record<string, string> = {
  github: 'GitHub',
  google: 'Google',
}
