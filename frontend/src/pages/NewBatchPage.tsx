import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { useAllRecipes } from '../hooks/useRecipes'
import { useUnitSystem } from '../hooks/useUnitSystem'
import { STATUSES, STATUS_LABELS, type BatchStatus } from '../lib/batches'
import { describeProblem } from '../lib/problem'
import { todayInputValue } from '../lib/time'
import { toStoredVolume } from '../lib/units'

type BatchCreate = components['schemas']['BatchCreate']

const input = 'mt-1 w-full rounded border border-stone-300 px-2 py-1'

export function NewBatchPage() {
  const [params] = useSearchParams()
  const recipes = useAllRecipes()
  const [system] = useUnitSystem()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [recipeId, setRecipeId] = useState(params.get('recipe') ?? '')
  const [name, setName] = useState('')
  const [brewDate, setBrewDate] = useState(todayInputValue())
  const [volumeText, setVolumeText] = useState('')
  const [status, setStatus] = useState<BatchStatus>('planned')
  const [notes, setNotes] = useState('')
  const vol = system === 'imperial' ? 'gal' : 'L'

  const create = useMutation({
    mutationFn: async () => {
      const body: BatchCreate = {
        recipe_id: recipeId,
        name: name.trim() || null,
        brew_date: brewDate || null,
        volume_l: volumeText === '' ? null : toStoredVolume(Number(volumeText), system),
        status,
        notes,
      }
      const { data, error, response } = await api.POST('/api/v1/batches', { body })
      if (!data) throw new Error(describeProblem(error, `Could not create the batch (${response.status})`))
      return data
    },
    onSuccess: async (batch) => {
      await queryClient.invalidateQueries({ queryKey: ['batches'] })
      void navigate(`/batches/${batch.id}`, { replace: true })
    },
  })

  const chosen = recipes.data?.find((r) => r.id === recipeId)
  return (
    <section className="max-w-xl space-y-4">
      <h1 className="text-2xl font-bold">New batch</h1>
      <p className="text-sm text-stone-600">
        The recipe is copied into the batch as it is now, so later edits to the recipe leave this
        batch unchanged.
      </p>
      {recipes.isSuccess && recipes.data.length === 0 && (
        <p className="text-stone-700">
          Save a recipe first: <Link to="/recipes/new" className="text-amber-700 hover:underline">open the designer</Link>.
        </p>
      )}
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
        <label className="block text-sm">
          Recipe
          <select className={input} value={recipeId} onChange={(e) => setRecipeId(e.target.value)} required>
            <option value="">Choose a recipe…</option>
            {recipes.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}{r.target_style ? ` (${r.target_style.display_name})` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Batch name
          <input className={input} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} placeholder={chosen ? chosen.name : 'Defaults to the recipe name'} />
        </label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block text-sm">
            Brew day
            <input type="date" className={input} value={brewDate} onChange={(e) => setBrewDate(e.target.value)} />
          </label>
          <label className="block text-sm">
            Volume ({vol})
            <input type="number" step="any" min="0" className={input} value={volumeText} onChange={(e) => setVolumeText(e.target.value)} placeholder="recipe volume" />
          </label>
          <label className="block text-sm">
            Status
            <select className={input} value={status} onChange={(e) => setStatus(e.target.value as BatchStatus)}>
              {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
          </label>
        </div>
        <label className="block text-sm">
          Notes
          <textarea className={`${input} min-h-20`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={10_000} />
        </label>
        {create.isError && <p role="alert" className="text-sm text-red-800">{(create.error as Error).message}</p>}
        <div className="flex gap-2">
          <button type="submit" disabled={!recipeId || create.isPending} className="rounded bg-amber-600 px-3 py-1 text-white disabled:opacity-50">
            Create batch
          </button>
          <Link to="/batches" className="px-3 py-1 text-sm">Cancel</Link>
        </div>
      </form>
    </section>
  )
}
