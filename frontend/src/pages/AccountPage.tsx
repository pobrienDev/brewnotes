import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { api } from '../api/client'
import { useInvalidateMe, useMe } from '../hooks/useMe'
import { useProviders } from '../hooks/useProviders'
import { useUnitSystem } from '../hooks/useUnitSystem'
import { PROVIDER_LABELS, linkUrl } from '../lib/auth'
import { describeProblem } from '../lib/problem'

const LINK_MESSAGES: Record<string, string> = {
  linked: 'Provider linked.',
  already_linked: 'That provider was already linked to this account.',
  in_use: 'That sign-in belongs to a different BrewNotes account, so it was not linked.',
  failed: 'Linking did not complete. Please try again while signed in.',
}

export function AccountPage() {
  const me = useMe()
  const providers = useProviders()
  const invalidateMe = useInvalidateMe()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [system, setSystem] = useUnitSystem()
  const [name, setName] = useState<string | null>(null)
  const [confirmText, setConfirmText] = useState('')

  const rename = useMutation({
    mutationFn: async (display_name: string) => {
      const { error } = await api.PATCH('/api/v1/me', { body: { display_name } })
      if (error) throw new Error(describeProblem(error))
    },
    onSuccess: async () => { setName(null); await invalidateMe() },
  })
  const unlink = useMutation({
    mutationFn: async (provider: 'github' | 'google') => {
      const { response, error } = await api.DELETE('/api/v1/me/identities/{provider}', { params: { path: { provider } } })
      if (!response.ok) throw new Error(describeProblem(error, 'Could not unlink'))
    },
    onSuccess: () => void invalidateMe(),
  })
  const logoutAll = useMutation({
    mutationFn: async () => { await api.POST('/api/v1/auth/logout-all') },
    onSuccess: async () => { queryClient.clear(); void navigate('/') },
  })
  const deleteAccount = useMutation({
    mutationFn: async () => {
      const { response } = await api.DELETE('/api/v1/me')
      if (!response.ok) throw new Error(`Deletion failed (${response.status})`)
    },
    onSuccess: async () => { queryClient.clear(); void navigate('/') },
  })
  const linkOutcome = params.get('link')

  if (!me.data) return null
  const user = me.data
  const linked = new Set(user.identities.map((i) => i.provider))

  return (
    <section className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold">Account</h1>
      {linkOutcome && <p role="status" className="rounded border border-amber-200 bg-amber-50 p-2 text-sm">{LINK_MESSAGES[linkOutcome] ?? linkOutcome}</p>}

      <section className="space-y-2">
        <h2 className="font-semibold">Display name</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); rename.mutate(name ?? user.display_name) }}>
          <input className="rounded border border-stone-300 px-2 py-1" value={name ?? user.display_name} onChange={(e) => setName(e.target.value)} maxLength={200} aria-label="Display name" />
          <button type="submit" className="rounded border border-stone-300 px-3 py-1 text-sm" disabled={rename.isPending || name === null}>Save</button>
        </form>
        {rename.isError && <p role="alert" className="text-sm text-red-800">{(rename.error as Error).message}</p>}
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Units</h2>
        <div className="flex gap-3 text-sm">
          {(['imperial', 'metric'] as const).map((s) => (
            <label key={s} className="flex items-center gap-1">
              <input type="radio" name="unit_pref" checked={system === s} onChange={() => setSystem(s)} />
              {s === 'imperial' ? 'US (lb, oz, gal, °F)' : 'Metric (kg, g, L, °C)'}
            </label>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Sign-in methods</h2>
        <ul className="space-y-1 text-sm">
          {providers.data?.map((p) => (
            <li key={p} className="flex items-center gap-3">
              <span className="w-20">{PROVIDER_LABELS[p] ?? p}</span>
              {linked.has(p) ? (
                <>
                  <span className="text-green-800">linked</span>
                  <button type="button" className="text-red-800 hover:underline disabled:opacity-50" disabled={linked.size < 2 || unlink.isPending} onClick={() => unlink.mutate(p as 'github' | 'google')} title={linked.size < 2 ? 'Link another method first' : undefined}>
                    unlink
                  </button>
                </>
              ) : (
                <a href={linkUrl(p)} className="text-amber-800 hover:underline">link</a>
              )}
            </li>
          ))}
        </ul>
        {unlink.isError && <p role="alert" className="text-sm text-red-800">{(unlink.error as Error).message}</p>}
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Sessions</h2>
        <button type="button" className="rounded border border-stone-300 px-3 py-1 text-sm" onClick={() => logoutAll.mutate()}>Log out everywhere</button>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Your data</h2>
        <a href="/api/v1/me/export" className="rounded border border-stone-300 px-3 py-1 text-sm">Download everything as JSON</a>
      </section>

      <section className="space-y-2 rounded border border-red-200 p-3">
        <h2 className="font-semibold text-red-900">Delete account</h2>
        <p className="text-sm text-stone-700">This removes your account, recipes and custom ingredients immediately. Type <strong>delete</strong> to confirm.</p>
        <div className="flex gap-2">
          <input className="rounded border border-stone-300 px-2 py-1" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} aria-label="Type delete to confirm" />
          <button type="button" className="rounded bg-red-700 px-3 py-1 text-sm text-white disabled:opacity-50" disabled={confirmText !== 'delete' || deleteAccount.isPending} onClick={() => deleteAccount.mutate()}>Delete my account</button>
        </div>
      </section>
    </section>
  )
}
