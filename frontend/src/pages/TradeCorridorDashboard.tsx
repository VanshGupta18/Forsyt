import Reveal from '../components/Reveal'
import WorldMap, { type MapMarkerData } from '../components/WorldMap'
import LiveClock from '../components/LiveClock'

const corridorMarkers: MapMarkerData[] = [
  {
    id: 'red-sea-route',
    name: 'Red Sea Route',
    coordinates: [40.0, 15.0],
    severity: 'critical',
    detail: 'Restricted. Vessels rerouting via Cape of Good Hope, +14 days for India-EU trade.',
  },
  {
    id: 'mundra-port',
    name: 'Mundra Port',
    coordinates: [69.7, 22.7],
    severity: 'moderate',
    detail: 'Severe weather and diverted traffic causing 48h docking delays.',
  },
  {
    id: 'suez-canal',
    name: 'Suez Canal',
    coordinates: [32.3, 30.5],
    severity: 'moderate',
    detail: 'Operational, medium risk. +2 days estimated delay.',
  },
  {
    id: 'imec-corridor',
    name: 'IMEC Corridor',
    coordinates: [55.3, 25.2],
    severity: 'moderate',
    detail: 'Developing. Saudi Arabia & India finalizing customs protocol for rail-to-ship transition.',
  },
  {
    id: 'malacca-strait',
    name: 'Malacca Strait',
    coordinates: [101.5, 2.5],
    severity: 'stable',
    detail: 'Operational, low risk. +1 day estimated delay.',
  },
]

export default function TradeCorridorDashboard() {
  return (
    <>


      <div className="pb-stack-lg px-margin-page max-w-container-max mx-auto space-y-stack-lg">

      <Reveal className="space-y-2 pt-2">
      <span className="eyebrow-badge">
      <span className="eyebrow-dot" />
      Live Corridor Monitoring
      </span>
      <h1 className="font-headline-lg text-headline-lg mb-2">Trade &amp; Corridor Risk Intelligence</h1>
      <p className="font-body-lg text-body-lg text-on-surface-variant">Monitor global trade routes, supply chains, logistics disruptions and geopolitical corridor risks impacting India.</p>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter">
      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-sm relative overflow-hidden">
      <div className="flex justify-between items-start">
      <span className="font-label-md text-label-md text-on-surface-variant uppercase">ACTIVE TRADE CORRIDORS</span>
      <span className="material-symbols-outlined text-outline" style={{fontVariationSettings: '\'FILL\' 0'}}>hub</span>
      </div>
      <div className="font-display-lg text-display-lg">14</div>
      <div className="text-secondary font-label-md text-label-md flex items-center gap-1 mt-auto">
      <span className="material-symbols-outlined text-[16px]">trending_up</span> + 2 New Proposed
                      </div>
      </div>
      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-sm relative overflow-hidden ai-accent">
      <div className="flex justify-between items-start">
      <span className="font-label-md text-label-md text-error uppercase">HIGH RISK SHIPPING ROUTES</span>
      <span className="material-symbols-outlined text-error" style={{fontVariationSettings: '\'FILL\' 0'}}>warning</span>
      </div>
      <div className="font-display-lg text-display-lg">06</div>
      <div className="text-error font-label-md text-label-md flex items-center gap-1 mt-auto">
      <span className="material-symbols-outlined text-[16px]">arrow_upward</span> Red Sea Elevated
                      </div>
      </div>
      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-sm relative overflow-hidden">
      <div className="flex justify-between items-start">
      <span className="font-label-md text-label-md text-tertiary uppercase">PORTS UNDER DISRUPTION</span>
      <span className="material-symbols-outlined text-tertiary" style={{fontVariationSettings: '\'FILL\' 0'}}>anchor</span>
      </div>
      <div className="font-display-lg text-display-lg">09</div>
      <div className="text-tertiary font-label-md text-label-md flex items-center gap-1 mt-auto">
      <span className="material-symbols-outlined text-[16px]">schedule</span> Avg 4.2 Days Delay
                      </div>
      </div>
      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-sm relative overflow-hidden">
      <div className="flex justify-between items-start">
      <span className="font-label-md text-label-md text-on-surface-variant uppercase">ESTIMATED TRADE IMPACT</span>
      <span className="material-symbols-outlined text-outline" style={{fontVariationSettings: '\'FILL\' 0'}}>bar_chart</span>
      </div>
      <div className="font-display-lg text-display-lg">-$1.4B</div>
      <div className="text-on-surface-variant font-label-md text-label-md flex items-center gap-1 mt-auto">
                          Projected Monthly Loss
                      </div>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="glass-panel rounded-lg p-stack-sm flex flex-wrap gap-stack-sm items-center justify-between">
      <div className="flex gap-stack-sm flex-wrap">
      <button className="bg-surface-variant hover:bg-surface-bright transition-colors px-4 py-2 rounded flex items-center gap-2 font-body-md text-body-md">
                          Trade Corridor: All Corridors <span className="material-symbols-outlined text-[18px]">expand_more</span>
      </button>
      <button className="bg-surface-variant hover:bg-surface-bright transition-colors px-4 py-2 rounded flex items-center gap-2 font-body-md text-body-md">
                          Transport Mode: Maritime <span className="material-symbols-outlined text-[18px]">expand_more</span>
      </button>
      <button className="bg-surface-variant hover:bg-surface-bright transition-colors px-4 py-2 rounded flex items-center gap-2 font-body-md text-body-md">
                          Commodity: All Types <span className="material-symbols-outlined text-[18px]">expand_more</span>
      </button>
      <button className="bg-surface-variant hover:bg-surface-bright transition-colors px-4 py-2 rounded flex items-center gap-2 font-body-md text-body-md">
                          Risk Level: Medium-High <span className="material-symbols-outlined text-[18px]">expand_more</span>
      </button>
      </div>
      <button className="text-on-surface-variant hover:text-on-surface transition-colors flex items-center gap-2 font-body-md text-body-md px-4 py-2">
      <span className="material-symbols-outlined text-[18px]">calendar_today</span> Last 30 Days
                  </button>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">

      <div className="lg:col-span-2 glass-panel rounded-lg relative overflow-hidden min-h-[500px] p-stack-md flex flex-col">
      <div className="mb-3">
      <h2 className="font-title-lg text-title-lg">Trade &amp; Corridor Intelligence Map</h2>
      <LiveClock />
      </div>

      <div className="flex-1 -mx-stack-md -mb-stack-md">
      <WorldMap markers={corridorMarkers} height={460} center={[50, 20]} zoom={1.8} />
      </div>
      </div>
      
      <div className="glass-panel rounded-lg flex flex-col h-[500px]">
      <div className="p-stack-md border-b border-white/5 flex justify-between items-center">
      <h2 className="font-title-lg text-title-lg">Live Corridor Alerts</h2>
      <span className="bg-surface-bright text-on-surface font-label-md text-label-md px-2 py-0.5 rounded text-[10px]">NEW</span>
      </div>
      <div className="p-stack-md flex-1 overflow-y-auto space-y-stack-md">
      
      <div className="bg-surface-container/50 border border-error/30 rounded-lg p-stack-sm flex flex-col gap-2 relative ai-accent !border-l-error">
      <div className="flex items-center gap-2 font-label-md text-label-md text-error uppercase">
      <span className="material-symbols-outlined text-[16px]">report</span> Critical Disruption
                              </div>
      <h3 className="font-body-lg text-body-lg font-semibold">Red Sea Shipping Stoppage</h3>
      <p className="font-body-md text-body-md text-on-surface-variant text-sm">Vessels rerouting via Cape of Good Hope. Average delay +14 days for India-EU trade.</p>
      <div className="flex justify-between items-center mt-2 font-label-md text-label-md text-on-surface-variant text-xs">
      <span>Impact: $650M</span>
      <span>3m ago</span>
      </div>
      </div>
      
      <div className="bg-surface-container/50 border border-tertiary/30 rounded-lg p-stack-sm flex flex-col gap-2 relative ai-accent !border-l-tertiary">
      <div className="flex items-center gap-2 font-label-md text-label-md text-tertiary uppercase">
      <span className="material-symbols-outlined text-[16px]">traffic</span> Port Congestion
                              </div>
      <h3 className="font-body-lg text-body-lg font-semibold">Mundra Port Backlog</h3>
      <p className="font-body-md text-body-md text-on-surface-variant text-sm">Severe weather and increased diverted traffic causing 48h docking delays.</p>
      <div className="flex justify-between items-center mt-2 font-label-md text-label-md text-on-surface-variant text-xs">
      <span>Impact: High</span>
      <span>1h ago</span>
      </div>
      </div>
      
      <div className="bg-surface-container/50 border border-primary/30 rounded-lg p-stack-sm flex flex-col gap-2 relative ai-accent">
      <div className="flex items-center gap-2 font-label-md text-label-md text-primary uppercase">
      <span className="material-symbols-outlined text-[16px]">policy</span> Corridor Update
                              </div>
      <h3 className="font-body-lg text-body-lg font-semibold">IMEC Regulatory Framework</h3>
      <p className="font-body-md text-body-md text-on-surface-variant text-sm">Saudi Arabia &amp; India finalize customs protocol for rail-to-ship transition.</p>
      </div>
      </div>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">

      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-md">
      <h2 className="font-title-lg text-title-lg border-b border-white/5 pb-2">Supply Chain Exposure by Sector</h2>
      <div className="space-y-4 mt-2">
      <div>
      <div className="flex justify-between font-body-md text-body-md mb-1">
      <span className="font-semibold">Pharmaceuticals</span>
      <span className="text-error font-label-md text-label-md">Critical Exposure (Red)</span>
      </div>
      <div className="h-2 w-full progress-bar-bg rounded-full overflow-hidden">
      <div className="h-full bg-error w-[85%] rounded-full"></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between font-body-md text-body-md mb-1">
      <span className="font-semibold">Electronics</span>
      <span className="text-tertiary font-label-md text-label-md">High Exposure (Amber)</span>
      </div>
      <div className="h-2 w-full progress-bar-bg rounded-full overflow-hidden">
      <div className="h-full bg-tertiary w-[70%] rounded-full"></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between font-body-md text-body-md mb-1">
      <span className="font-semibold">Energy</span>
      <span className="text-tertiary font-label-md text-label-md">Moderate Exposure (Yellow)</span>
      </div>
      <div className="h-2 w-full progress-bar-bg rounded-full overflow-hidden">
      <div className="h-full bg-tertiary w-[50%] rounded-full opacity-80"></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between font-body-md text-body-md mb-1">
      <span className="font-semibold">Agriculture</span>
      <span className="text-tertiary font-label-md text-label-md">Moderate Exposure (Yellow)</span>
      </div>
      <div className="h-2 w-full progress-bar-bg rounded-full overflow-hidden">
      <div className="h-full bg-tertiary w-[50%] rounded-full opacity-80"></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between font-body-md text-body-md mb-1">
      <span className="font-semibold">Automobile</span>
      <span className="text-secondary font-label-md text-label-md">Low Exposure (Green)</span>
      </div>
      <div className="h-2 w-full progress-bar-bg rounded-full overflow-hidden">
      <div className="h-full bg-secondary w-[25%] rounded-full"></div>
      </div>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-md">
      <h2 className="font-title-lg text-title-lg border-b border-white/5 pb-2">Trade Route Status</h2>
      <div className="overflow-x-auto mt-2">
      <table className="w-full text-left font-body-md text-body-md">
      <thead>
      <tr className="text-on-surface-variant border-b border-white/5">
      <th className="pb-2 font-medium">Corridor Name</th>
      <th className="pb-2 font-medium">Operational Status</th>
      <th className="pb-2 font-medium">Risk Level</th>
      <th className="pb-2 font-medium">Estimated Delay</th>
      </tr>
      </thead>
      <tbody className="divide-y divide-white/5">
      <tr>
      <td className="py-3 font-semibold">Red Sea Route</td>
      <td className="py-3 text-error">Restricted</td>
      <td className="py-3 text-error">High</td>
      <td className="py-3 text-error">+14 Days</td>
      </tr>
      <tr>
      <td className="py-3 font-semibold">Suez Canal</td>
      <td className="py-3 text-secondary">Operational</td>
      <td className="py-3 text-tertiary">Medium</td>
      <td className="py-3 text-tertiary">+2 Days</td>
      </tr>
      <tr>
      <td className="py-3 font-semibold">IMEC Corridor</td>
      <td className="py-3 text-tertiary">Developing</td>
      <td className="py-3 text-tertiary">Medium-High</td>
      <td className="py-3 text-on-surface-variant">N/A</td>
      </tr>
      <tr>
      <td className="py-3 font-semibold">Malacca Strait</td>
      <td className="py-3 text-secondary">Operational</td>
      <td className="py-3 text-secondary">Low</td>
      <td className="py-3 text-secondary">+1 Day</td>
      </tr>
      </tbody>
      </table>
      </div>
      </div>
      
      <div className="card-lift glass-panel rounded-lg p-stack-md flex flex-col gap-stack-md ai-accent">
      <h2 className="font-title-lg text-title-lg border-b border-white/5 pb-2 flex items-center gap-2">
      <span className="material-symbols-outlined text-primary text-[20px]">smart_toy</span> AI Recommendations
                      </h2>
      <ul className="space-y-3 mt-2 font-body-md text-body-md list-disc list-inside text-on-surface-variant">
      <li><span className="text-on-surface">Reroute critical shipments</span> via Cape of Good Hope.</li>
      <li><span className="text-on-surface">Advance inventory buffer</span> for electronics components.</li>
      <li><span className="text-on-surface">Diversify sourcing</span> for critical minerals in South America.</li>
      <li><span className="text-on-surface">Monitor Malacca Strait</span> for potential weather delays.</li>
      </ul>
      </div>
      </section>
      </Reveal>
      </div>


    </>
  )
}
