import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import { api } from '../api/client'
import { useInvalidateMe } from '../hooks/useMe'

export function SignOutButton() {
  const invalidateMe = useInvalidateMe()
  const navigate = useNavigate()
  const signOut = useMutation({
    mutationFn: async () => {
      const { response } = await api.POST('/api/v1/auth/logout')
      if (!response.ok) throw new Error('Sign-out failed')
    },
    onSuccess: async () => {
      await invalidateMe()
      void navigate('/')
    },
  })
  return (
    <button
      type="button"
      onClick={() => signOut.mutate()}
      disabled={signOut.isPending}
      className="rounded border border-stone-300 px-2 py-1 text-sm hover:bg-stone-100 disabled:opacity-50"
    >
      Sign out
    </button>
  )
}
