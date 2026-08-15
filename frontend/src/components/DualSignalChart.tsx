import { useState } from 'react'
import GprHistoryChart from './GprHistoryChart'
import MarketSparkline from './MarketSparkline'

const RANGES = [
  { id: '1mo', label: '1M' },
  { id: '3mo', label: '3M' },
  { id: '6mo', label: '6M' },
  { id: '1y', label: '1Y' },
] as const

type RangeId = (typeof RANGES)[number]['id']

type Props = {
  chartHeight?: number
}

export default function DualSignalChart({ chartHeight = 260 }: Props) {
  const [range, setRange] = useState<RangeId>('3mo')

  return (
    <div className="corridor-panel p-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="corridor-kicker">Dual signal</p>
          <h2 className="corridor-headline mt-1">NIFTY vs Forsyt GPR</h2>
          <p className="text-[10px] text-corridor-muted mt-1">
            Market price and news-driven risk index side by side
          </p>
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

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <p className="corridor-kicker mb-2">NIFTY 50</p>
          <MarketSparkline symbol="nifty" period={range} height={chartHeight} variant="corridor" />
        </div>
        <div>
          <p className="corridor-kicker mb-2">Forsyt GPR</p>
          <GprHistoryChart height={chartHeight} variant="corridor" />
        </div>
      </div>
    </div>
  )
}
