import { STATUS_LABELS, type BatchStatus } from '../lib/batches'

const COLOURS: Record<BatchStatus, string> = {
  planned: 'bg-stone-100 text-stone-800',
  fermenting: 'bg-amber-100 text-amber-900',
  conditioning: 'bg-yellow-100 text-yellow-900',
  packaged: 'bg-lime-100 text-lime-900',
  done: 'bg-green-100 text-green-900',
}

export function StatusBadge({ status }: { status: BatchStatus }) {
  return (
    <span data-testid="status-badge" className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${COLOURS[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}
