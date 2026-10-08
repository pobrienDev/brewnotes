import { useMutation } from '@tanstack/react-query'
import { useCallback, useState } from 'react'

import { api } from '../api/client'
import type { UnitSystem } from '../lib/units'
import { useInvalidateMe, useMe } from './useMe'

const STORAGE_KEY = 'brewnotes.units'

function readStored(): UnitSystem {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === 'metric' ? 'metric' : 'imperial'
  } catch {
    return 'imperial'
  }
}

/**
 * The display unit system: the account's preference when signed in, otherwise a per-browser
 * choice. Changing it while signed in saves to the account.
 */
export function useUnitSystem(): [UnitSystem, (system: UnitSystem) => void] {
  const me = useMe()
  const invalidateMe = useInvalidateMe()
  const [local, setLocal] = useState<UnitSystem>(readStored)
  const save = useMutation({
    mutationFn: async (unit_pref: UnitSystem) => {
      const { error } = await api.PATCH('/api/v1/me', { body: { unit_pref } })
      if (error) throw new Error(error.title)
    },
    onSuccess: () => void invalidateMe(),
  })

  // Signed in: the account's preference wins. Anonymous: the browser's choice.
  const system: UnitSystem = me.data ? me.data.unit_pref : local

  const set = useCallback(
    (system: UnitSystem) => {
      setLocal(system)
      try {
        window.localStorage.setItem(STORAGE_KEY, system)
      } catch {
        // storage unavailable: the choice lasts for this page only
      }
      if (me.data) save.mutate(system)
    },
    [me.data, save],
  )
  return [system, set]
}
