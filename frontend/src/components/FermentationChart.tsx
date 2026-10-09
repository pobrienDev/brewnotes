import {
  type ChartOptions,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  TimeScale,
  Tooltip,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import { Line } from 'react-chartjs-2'

import { type ReadingOut, chartSeries } from '../lib/batches'
import type { UnitSystem } from '../lib/units'

ChartJS.register(LineElement, PointElement, LinearScale, TimeScale, Tooltip, Legend)

/**
 * Gravity (left axis) and temperature (right axis) over time. The server has already
 * downsampled the series; the readings table under the chart is the text equivalent.
 */
export function FermentationChart({ readings, system }: { readings: ReadingOut[]; system: UnitSystem }) {
  const series = chartSeries(readings, system)
  const hasTemp = series.temperature.some((p) => p.y !== null)
  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
    scales: {
      x: { type: 'time', time: { tooltipFormat: 'PP p' }, ticks: { maxTicksLimit: 8 } },
      y: {
        type: 'linear',
        position: 'left',
        title: { display: true, text: 'Gravity (SG)' },
        ticks: { callback: (v) => Number(v).toFixed(3) },
      },
      y1: {
        type: 'linear',
        position: 'right',
        display: hasTemp,
        grid: { drawOnChartArea: false },
        title: { display: true, text: `Temperature (${series.temperatureUnit})` },
      },
    },
    plugins: { legend: { position: 'bottom' } },
  }
  const gravity = {
    label: 'Gravity',
    data: series.gravity,
    yAxisID: 'y',
    borderColor: '#b45309',
    backgroundColor: '#b45309',
    spanGaps: true,
    pointRadius: readings.length > 60 ? 0 : 3,
    tension: 0.2,
  }
  const temp = {
    label: `Temperature (${series.temperatureUnit})`,
    data: series.temperature,
    yAxisID: 'y1',
    borderColor: '#0369a1',
    backgroundColor: '#0369a1',
    spanGaps: true,
    pointRadius: readings.length > 60 ? 0 : 3,
    tension: 0.2,
  }
  // No temperature series at all (gravity-only logs) means no second axis or legend entry.
  const data = { datasets: hasTemp ? [gravity, temp] : [gravity] }
  return (
    <div className="h-72 w-full">
      <Line
        role="img"
        aria-label={`Fermentation chart with ${readings.length} readings; the table below lists them.`}
        options={options}
        data={data}
      />
    </div>
  )
}
