// Markets-page section: the news risk index and the India oil-GPR index as
// two interactive line charts (hover crosshair + tooltip), sharing one
// time-range picker (1M/3M/6M/1Y) so both windows stay aligned.
import { useState } from 'react'
import GprHistoryChart, { type GprChartPeriod } from './GprHistoryChart'
import type { GprHistoryPoint } from '../lib/api'

const RANGES = [
  { id: '1mo', label: '1M' },
  { id: '3mo', label: '3M' },
  { id: '6mo', label: '6M' },
  { id: '1y', label: '1Y' },
] as const

type RangeId = (typeof RANGES)[number]['id']

type Props = {
  chartHeight?: number
  indexDays?: number | null
  gprHistory?: GprHistoryPoint[]
  oilHistory?: GprHistoryPoint[]
}

export default function RiskChartsPanel({ chartHeight = 260, indexDays, gprHistory, oilHistory }: Props) {
  // Oil-GPR carries ~8 months of history and the news index only ~30 days, so
  // the picker is free (no forced 1M) — each chart shows what it has within
  // the shared window. Default 3M.
  const [range, setRange] = useState<RangeId>('3mo')
  const [rangeNote, setRangeNote] = useState<string | null>(null)

  return (
    <div className="corridor-panel p-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="corridor-kicker">Risk signals</p>
          <h2 className="corridor-headline mt-1">News risk vs oil-GPR</h2>
          <p className="text-[10px] text-corridor-muted mt-1">Latest {range.replace('mo', 'M').replace('1y', '1Y')} of each index · hover for values</p>
        </div>
        <div className="flex items-center gap-1">
          {RANGES.map((r) => (
            <button
              key={r.id}
              type="button"
              className="corridor-tab px-3 py-1.5"
              data-active={range === r.id ? 'true' : 'false'}
              onClick={() => setRange(r.id)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {rangeNote && <p className="text-[10px] text-corridor-watch">{rangeNote}</p>}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <p className="corridor-kicker mb-2">News risk index</p>
          <GprHistoryChart
            height={chartHeight}
            variant="corridor"
            period={range as GprChartPeriod}
            history={gprHistory ?? []}
            indexDays={indexDays}
            onRangeNote={setRangeNote}
          />
        </div>
        <div>
          <p className="corridor-kicker mb-2">India oil-GPR</p>
          <GprHistoryChart
            height={chartHeight}
            variant="corridor"
            period={range as GprChartPeriod}
            history={oilHistory ?? []}
            label="India oil-GPR"
            valueLabel="Oil-GPR"
            showBaseline={false}
          />
        </div>
      </div>
    </div>
  )
}
