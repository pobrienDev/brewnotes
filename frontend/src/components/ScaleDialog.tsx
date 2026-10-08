import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { api } from '../api/client'
import type { components } from '../api/schema'
import { describeProblem } from '../lib/problem'
import { type UnitSystem, toStoredVolume, volume } from '../lib/units'

type RecipeInput = components['schemas']['RecipeInput']
type ScaleResult = components['schemas']['ScaleResult']

export function ScaleDialog({
  body,
  system,
  onApply,
}: {
  body: RecipeInput | null
  system: UnitSystem
  onApply: (scaled: ScaleResult['recipe']) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const [newVolume, setNewVolume] = useState('')
  const [newEfficiency, setNewEfficiency] = useState('')
  const unit = system === 'imperial' ? 'gal' : 'L'
  const scale = useMutation({
    mutationFn: async () => {
      if (!body) throw new Error('Complete the recipe first')
      const vol = newVolume === '' ? undefined : toStoredVolume(Number(newVolume), system)
      const eff = newEfficiency === '' ? undefined : Number(newEfficiency)
      const { data, error, response } = await api.POST('/api/v1/calc/scale', {
        body: { recipe: body, batch_volume_l: vol ?? null, brewhouse_efficiency_pct: eff ?? null },
      })
      if (!data) throw new Error(describeProblem(error, `Scaling failed (${response.status})`))
      return data
    },
    onSuccess: (result) => {
      onApply(result.recipe)
      ref.current?.close()
    },
  })
  const currentVolume = body ? volume(body.batch_volume_l, system).value.toFixed(2) : ''
  const canApply = !scale.isPending && (newVolume !== '' || newEfficiency !== '')
  return (
    <>
      <button
        type="button"
        className="rounded border border-stone-300 px-3 py-1 text-sm hover:bg-stone-100 disabled:opacity-50"
        disabled={!body}
        onClick={() => ref.current?.showModal()}
      >
        Scale…
      </button>
      <dialog ref={ref} className="rounded border border-stone-300 p-0 backdrop:bg-black/30">
        <div
          role="group"
          aria-labelledby="scale-title"
          className="w-80 space-y-3 p-4"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && canApply) {
              e.preventDefault()
              scale.mutate()
            }
          }}
        >
          <h2 id="scale-title" className="text-lg font-semibold">
            Scale recipe
          </h2>
          <label className="block text-sm">
            New batch volume ({unit}) <span className="text-stone-500">now {currentVolume}</span>
            <input
              type="number"
              step="any"
              min="0"
              value={newVolume}
              onChange={(e) => setNewVolume(e.target.value)}
              className="mt-1 w-full rounded border border-stone-300 px-2 py-1"
            />
          </label>
          <label className="block text-sm">
            New brewhouse efficiency (%) <span className="text-stone-500">now {body?.brewhouse_efficiency_pct}</span>
            <input
              type="number"
              step="any"
              min="20"
              max="100"
              value={newEfficiency}
              onChange={(e) => setNewEfficiency(e.target.value)}
              className="mt-1 w-full rounded border border-stone-300 px-2 py-1"
            />
          </label>
          {scale.isError && (
            <p role="alert" className="text-sm text-red-800">
              {(scale.error as Error).message}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" className="px-3 py-1 text-sm" onClick={() => ref.current?.close()}>
              Cancel
            </button>
            <button
              type="button"
              className="rounded bg-amber-600 px-3 py-1 text-sm text-white disabled:opacity-50"
              disabled={!canApply}
              onClick={() => scale.mutate()}
            >
              Apply
            </button>
          </div>
        </div>
      </dialog>
    </>
  )
}
