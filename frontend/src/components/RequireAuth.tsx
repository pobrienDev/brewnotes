import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useMe } from '../hooks/useMe'

export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe()
  const location = useLocation()
  if (me.isPending) return <p className="text-stone-500">Loading…</p>
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/sign-in?next=${next}`} replace />
  }
  return <>{children}</>
}
