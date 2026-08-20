import { useEffect, useState } from 'react'
import GprHistoryChart, { type GprChartPeriod } from './GprHistoryChart'
import MarketSparkline from './MarketSparkline'
import type { GprHistoryPoint, MarketHistoryPayload } from '../lib/api'

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
  niftyHistory?: MarketHistoryPayload | null
}

function defaultRange(indexDays?: number | null): RangeId {
  if (indexDays != null && indexDays < 90) return '1mo'
  return '3mo'
}

export default function DualSignalChart({ chartHeight = 260, indexDays, gprHistory, niftyHistory }: Props) {
  const [range, setRange] = useState<RangeId>(() => defaultRange(indexDays))
  const [rangeNote, setRangeNote] = useState<string | null>(null)

  useEffect(() => {
    if (indexDays != null && indexDays < 90 && range !== '1mo') {
      setRange('1mo')
    }
  }, [indexDays, range])

  return (
    <div className="corridor-panel p-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="corridor-kicker">Dual signal</p>
          <h2 className="corridor-headline mt-1">NIFTY vs news risk index</h2>
          <p className="text-[10px] text-corridor-muted mt-1">Same time window for both charts</p>
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
          <p className="corridor-kicker mb-2">NIFTY 50</p>
          <MarketSparkline data={niftyHistory} period={range} height={chartHeight} variant="corridor" />
        </div>
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
      </div>
    </div>
  )
}
