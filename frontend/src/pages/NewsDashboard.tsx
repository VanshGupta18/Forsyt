import { useEffect, useState } from 'react'
import { fetchGprCurrent, fetchRecentNews, type NewsArticle } from '../lib/api'
import Reveal from '../components/Reveal'
import WorldMap, { type MapMarkerData, type MapSeverity } from '../components/WorldMap'
import LiveClock from '../components/LiveClock'

const newsMarkers: MapMarkerData[] = [
  {
    id: 'red-sea',
    name: 'Red Sea Shipping Corridor',
    coordinates: [43.3, 12.6],
    severity: 'critical',
    detail: 'Suspected drone activity targeting commercial freight in the Bab al-Mandab strait.',
  },
  {
    id: 'ladakh',
    name: 'India-China Border',
    coordinates: [78.3, 34.2],
    severity: 'moderate',
    detail: 'High-altitude logistics support vehicles deployed in the eastern sector.',
  },
  {
    id: 'taiwan-strait',
    name: 'Taiwan Strait',
    coordinates: [121.0, 23.7],
    severity: 'critical',
    detail: 'Semiconductor export regulation tensions affecting global supply chains.',
  },
  {
    id: 'suez',
    name: 'Suez Canal',
    coordinates: [32.3, 30.5],
    severity: 'stable',
    detail: 'Normal transit operations, no disruptions reported.',
  },
  {
    id: 'south-china-sea',
    name: 'South China Sea',
    coordinates: [114.0, 12.0],
    severity: 'critical',
    detail: 'Elevated naval activity around contested maritime zones.',
  },
]

export default function NewsDashboard() {
  const [activeSeverities, setActiveSeverities] = useState<Set<MapSeverity>>(
    new Set(['critical', 'moderate', 'stable']),
  )
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [gprIndex, setGprIndex] = useState<number | null>(null)
  const [feedError, setFeedError] = useState<string | null>(null)

  useEffect(() => {
    fetchRecentNews(12)
      .then((payload) => setArticles(payload.articles ?? []))
      .catch((err: Error) => setFeedError(err.message))
    fetchGprCurrent()
      .then((gpr) => setGprIndex(gpr.gpr_index ?? null))
      .catch(() => undefined)
  }, [])

  function toggleSeverity(s: MapSeverity) {
    setActiveSeverities((prev) => {
      const next = new Set(prev)
      if (next.has(s)) {
        if (next.size > 1) next.delete(s)
      } else {
        next.add(s)
      }
      return next
    })
  }

  return (
    <>




      <div className="flex-1 w-full max-w-[1400px] mx-auto px-6 py-6 flex flex-col gap-6">

      <Reveal className="pt-2 pb-1 space-y-2">
      <span className="eyebrow-badge">
      <span className="eyebrow-dot" />
      Live News Intelligence
      </span>
      <h1 className="text-2xl font-bold text-white">News Intelligence</h1>
      <p className="text-sm text-[#8b97ab] max-w-2xl">Real-time geopolitical event tracking, curated and scored for relevance to Indian sovereign and institutional interests.</p>
      </Reveal>

      <section aria-label="Filters" className="flex flex-col md:flex-row gap-3 w-full">
      
      <div className="relative flex-1 md:max-w-md">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8b97ab]">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" strokeLinecap="round" strokeLinejoin="round"></path>
      </svg>
      </div>
      <input className="block w-full pl-9 pr-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#e2e8f0] placeholder-dashboard-muted focus:ring-1 focus:ring-[#3b82f6] focus:border-[#3b82f6] outline-none transition-all" placeholder="Search news intelligence..." type="text"/>
      </div>
      
      <div className="flex flex-wrap gap-3">
      <button className="flex items-center gap-2 px-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#8b97ab] hover:text-[#e2e8f0] hover:border-gray-600 transition-colors">
                Country
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path clipRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" fillRule="evenodd"></path></svg>
      </button>
      <button className="flex items-center gap-2 px-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#8b97ab] hover:text-[#e2e8f0] hover:border-gray-600 transition-colors">
                Risk Level
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path clipRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" fillRule="evenodd"></path></svg>
      </button>
      <button className="flex items-center gap-2 px-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#8b97ab] hover:text-[#e2e8f0] hover:border-gray-600 transition-colors">
                Region
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path clipRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" fillRule="evenodd"></path></svg>
      </button>
      <button className="flex items-center gap-2 px-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#8b97ab] hover:text-[#e2e8f0] hover:border-gray-600 transition-colors">
                Category
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path clipRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" fillRule="evenodd"></path></svg>
      </button>
      <button className="flex items-center gap-2 px-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#8b97ab] hover:text-[#e2e8f0] hover:border-gray-600 transition-colors ml-auto md:ml-0">
                Date Range
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zm2.25-4.5h.008v.008H16.5v-.008zm0 2.25h.008v.008H16.5V15z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
      </button>
      </div>
      </section>
      
      
      <Reveal>
      <section aria-label="Key Performance Indicators" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

      <div className="card-lift bg-[#111520] border border-[#2e4063] rounded-xl p-5 shadow-glow-blue flex items-center justify-between relative overflow-hidden group hover:border-[#3b82f6]/50 transition-colors">
      <div className="flex flex-col gap-1 z-10">
      <span className="text-xs font-semibold text-[#8b97ab] uppercase tracking-wider">Active Global Events</span>
      <span className="text-3xl font-bold text-white">{articles.length || "—"}</span>
      </div>
      <div className="w-10 h-10 rounded-full bg-[#3b82f6]/10 flex items-center justify-center text-[#3b82f6] z-10">
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" strokeLinecap="round" strokeLinejoin="round"></path></svg>
      </div>
      
      <div className="absolute right-4 bottom-4 opacity-30 text-[#3b82f6]">
      <svg fill="none" height="20" stroke="currentColor" strokeWidth="2" viewBox="0 0 40 20" width="40"><path d="M0 20 L10 10 L20 15 L30 5 L40 0"></path></svg>
      </div>
      </div>
      
      <div className="card-lift bg-[#111520] border border-[#4a2424] rounded-xl p-5 shadow-glow-red flex items-center justify-between relative overflow-hidden group hover:border-[#ef4444]/50 transition-colors">
      <div className="flex flex-col gap-1 z-10">
      <span className="text-xs font-semibold text-[#8b97ab] uppercase tracking-wider">High Risk Events</span>
      <span className="text-3xl font-bold text-[#ef4444]">8</span>
      </div>
      <div className="w-10 h-10 rounded-full bg-[#ef4444]/10 flex items-center justify-center text-[#ef4444] z-10">
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
      </div>
      </div>
      
      <div className="card-lift bg-[#111520] border border-[#1b3d31] rounded-xl p-5 shadow-glow-green flex items-center justify-between relative overflow-hidden group hover:border-[#10b981]/50 transition-colors">
      <div className="flex flex-col gap-1 z-10">
      <span className="text-xs font-semibold text-[#8b97ab] uppercase tracking-wider">Countries Under Watch</span>
      <span className="text-3xl font-bold text-white">124</span>
      </div>
      <div className="w-10 h-10 rounded-full bg-[#10b981]/10 flex items-center justify-center text-[#10b981] z-10">
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
      </div>
      </div>
      
      <div className="card-lift bg-[#111520] border border-[#2e4063] rounded-xl p-5 shadow-glow-blue flex items-center justify-between relative overflow-hidden group hover:border-[#3b82f6]/50 transition-colors">
      <div className="flex flex-col gap-1 z-10">
      <span className="text-xs font-semibold text-[#8b97ab] uppercase tracking-wider">Avg India GPR Score</span>
      <div className="flex items-baseline gap-1">
      <span className="text-3xl font-bold text-[#f59e0b]">68</span>
      <span className="text-sm text-[#8b97ab] font-medium">/ 100</span>
      </div>
      </div>
      <div className="w-10 h-10 rounded-full bg-[#3b82f6]/10 flex items-center justify-center text-[#3b82f6] z-10">
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" strokeLinecap="round" strokeLinejoin="round"></path></svg>
      </div>
      </div>
      </section>
      </Reveal>


      <Reveal>
      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6 h-auto min-h-[450px]">

      <div className="xl:col-span-2 bg-[#111520] border border-[#1f2638] rounded-xl p-5 flex flex-col relative overflow-hidden">

      <div className="flex items-center justify-between mb-4 z-10 relative">
      <div>
      <h2 className="text-lg font-semibold text-white">Intelligence Coverage</h2>
      <LiveClock className="font-label-md text-[10px] text-[#8b97ab] tracking-wider" />
      </div>

      <div className="flex gap-2 text-xs font-medium">
      <button onClick={() => toggleSeverity('critical')} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${activeSeverities.has('critical') ? 'border-[#ef4444]/50 bg-[#ef4444]/10 text-[#e2e8f0] shadow-[0_0_10px_-2px_rgba(239,68,68,0.5)]' : 'border-[#1f2638] text-[#8b97ab] opacity-50 hover:opacity-80'}`}>
      <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444] shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span> Critical
      </button>
      <button onClick={() => toggleSeverity('moderate')} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${activeSeverities.has('moderate') ? 'border-[#f59e0b]/50 bg-[#f59e0b]/10 text-[#e2e8f0] shadow-[0_0_10px_-2px_rgba(245,158,11,0.5)]' : 'border-[#1f2638] text-[#8b97ab] opacity-50 hover:opacity-80'}`}>
      <span className="w-2.5 h-2.5 rounded-full bg-[#f59e0b] shadow-[0_0_8px_rgba(245,158,11,0.8)]"></span> Moderate
      </button>
      <button onClick={() => toggleSeverity('stable')} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${activeSeverities.has('stable') ? 'border-[#10b981]/50 bg-[#10b981]/10 text-[#e2e8f0] shadow-[0_0_10px_-2px_rgba(16,185,129,0.5)]' : 'border-[#1f2638] text-[#8b97ab] opacity-50 hover:opacity-80'}`}>
      <span className="w-2.5 h-2.5 rounded-full bg-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span> Stable
      </button>
      </div>
      </div>

      <div className="flex-1 relative rounded-lg overflow-hidden border border-[#1f2638]/50 bg-[#0a0e17]">
      <WorldMap markers={newsMarkers} activeSeverities={activeSeverities} height={340} />
      </div>
      </div>
      
      <div className="xl:col-span-1 bg-[#111520] border border-[#1f2638] rounded-xl p-5 flex flex-col h-[450px]">
      
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#1f2638]/50">
      <h2 className="text-base font-semibold text-white">Top Risk Events</h2>
      <a className="text-sm font-medium text-white hover:text-[#3b82f6] transition-colors" href="#">View All</a>
      </div>
      
      <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-3 pr-1">
      
      <div className="bg-[#0a0d14]/50 border border-[#1f2638] rounded-lg p-3 hover:border-[#8b97ab]/50 transition-colors cursor-pointer group">
      <div className="flex justify-between items-start mb-2">
      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#f59e0b]/20 text-[#f59e0b] border border-[#f59e0b]/30">HIGH</span>
      <span className="text-xs text-[#8b97ab] group-hover:text-[#e2e8f0] transition-colors">2m ago</span>
      </div>
      <h3 className="text-sm font-semibold text-white leading-tight mb-1">India-China Border Tactical Movement</h3>
      <p className="text-xs text-[#8b97ab] line-clamp-2 mb-3 leading-relaxed">Reported deployment of high-altitude logistics support vehicles in the eastern sector.</p>
      <div className="flex items-center gap-3 text-[11px] text-[#8b97ab] font-medium">
      <div className="flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" strokeLinecap="round" strokeLinejoin="round"></path><path d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                      Ladakh
                    </div>
      <div className="flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                      Defense
                    </div>
      </div>
      </div>
      
      <div className="bg-[#0a0d14]/50 border border-[#1f2638] rounded-lg p-3 hover:border-[#8b97ab]/50 transition-colors cursor-pointer group">
      <div className="flex justify-between items-start mb-2">
      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#ef4444]/20 text-[#ef4444] border border-[#ef4444]/30">CRITICAL</span>
      <span className="text-xs text-[#8b97ab] group-hover:text-[#e2e8f0] transition-colors">45m ago</span>
      </div>
      <h3 className="text-sm font-semibold text-white leading-tight mb-1">Red Sea Shipping Corridor Alert</h3>
      <p className="text-xs text-[#8b97ab] line-clamp-2 mb-3 leading-relaxed">Suspected drone activity targeting commercial freight vessels in the Bab al-Mandab strait.</p>
      <div className="flex items-center gap-3 text-[11px] text-[#8b97ab] font-medium">
      <div className="flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" strokeLinecap="round" strokeLinejoin="round"></path><path d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                      Yemen / Bab al-Mandab
                    </div>
      <div className="flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                      Trade
                    </div>
      </div>
      </div>
      
      <div className="bg-[#0a0d14]/50 border border-[#1f2638] rounded-lg p-3 hover:border-[#8b97ab]/50 transition-colors cursor-pointer group">
      <div className="flex justify-between items-start mb-2">
      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#f59e0b]/20 text-[#f59e0b] border border-[#f59e0b]/30">HIGH</span>
      <span className="text-xs text-[#8b97ab] group-hover:text-[#e2e8f0] transition-colors">2h ago</span>
      </div>
      <h3 className="text-sm font-semibold text-white leading-tight mb-1">Semiconductor Export Regulation Update</h3>
      <p className="text-xs text-[#8b97ab] line-clamp-2 mb-3 leading-relaxed">New bilateral restrictions introduced affecting raw material supply chains.</p>
      <div className="flex items-center gap-3 text-[11px] text-[#8b97ab] font-medium">
      <div className="flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" strokeLinecap="round" strokeLinejoin="round"></path><path d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                      Global / US-CN
                    </div>
      <div className="flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M5.25 12h3.632c.124.032.247.078.368.138l3.602 1.801a1.125 1.125 0 001.078.018l3.75-2.25M5.25 12H3m2.25 0V8.25m0 3.75v3.75m0-3.75h13.5m-13.5 0v-1.5m13.5 1.5v1.5m0-1.5V8.25m0 3.75h1.5m-1.5 0v-1.5M15.75 3v1.5M12 18.75v1.5M12 18.75v-1.5m0 1.5h-1.5m1.5 0h1.5" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                      Tech
                    </div>
      </div>
      </div>
      </div>
      </div>
      </section>
      </Reveal>


      <Reveal>
      <section className="bg-[#111520]/60 backdrop-blur-sm border border-[#1f2638] rounded-xl p-6 relative overflow-hidden group hover:border-[#8b97ab]/30 transition-colors">

      <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-[#3b82f6]/50 to-transparent"></div>
      <div className="flex items-start gap-4">
      
      <div className="p-2 bg-[#0a0d14]/80 rounded-lg border border-[#1f2638] text-white mt-0.5">
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.428-1.428L13.5 18.75l1.178-.394a2.25 2.25 0 001.428-1.428L16.5 15.75l.394 1.178a2.25 2.25 0 001.428 1.428l1.178.394-1.178.394a2.25 2.25 0 00-1.428 1.428z" strokeLinecap="round" strokeLinejoin="round"></path>
      </svg>
      </div>
      <div className="flex-1">
      <h3 className="text-sm font-medium text-white mb-2">Today's Intelligence Summary</h3>
      <p className="text-sm text-[#e2e8f0] leading-relaxed">
                  Geopolitical volatility continues to shift towards the <span className="font-semibold text-white">Red Sea corridor</span>, with fresh shipping disruptions impacting Indian energy imports. While domestic macroeconomic indicators remain robust, the <span className="text-[#ef4444] font-medium bg-[#ef4444]/10 px-1.5 py-0.5 rounded border border-[#ef4444]/20">elevated border risk score (76)</span> suggests cautious defensive posturing in technical sectors. Intelligence confirms a 12% rise in regional trade risk due to shifting maritime alliances.
                </p>
      </div>
      </div>
      </section>
      </Reveal>


      <Reveal>
      <section>

      <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-white">News Intelligence Feed</h2>
      <div className="flex items-center gap-4">
      <div className="flex items-center gap-2 text-sm text-[#8b97ab]">
                  Live Updates: <span className="text-[#10b981] font-medium">Enabled</span>
      </div>
      
      <div className="flex bg-[#111520] border border-[#1f2638] rounded-lg p-0.5">
      <button className="px-3 py-1 text-xs font-medium text-[#8b97ab] hover:text-white rounded-md transition-colors">List</button>
      <button className="px-3 py-1 text-xs font-medium text-white bg-[#0a0d14] border border-[#1f2638] rounded-md shadow-sm">Grid</button>
      </div>
      </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      
      {feedError && (
        <p className="text-sm text-[#f59e0b] mb-4">API feed unavailable ({feedError}). Start Flask on :5000 or use Vite proxy.</p>
      )}

      {articles.length > 0 ? (
        articles.map((article) => (
          <article key={article.link || article.title} className="bg-[#111520] border border-[#1f2638] rounded-xl overflow-hidden flex flex-col group hover:-translate-y-1 transition-transform duration-300">
            <div className="p-5 flex-1 flex flex-col">
              <div className="flex items-center justify-between text-xs font-medium text-[#8b97ab] uppercase tracking-wider mb-2">
                <span>{article.nlp_themes?.split(',')[0]?.trim() || 'Geopolitical'}</span>
                <span>{(article.published_at || article.scraped_at || '').slice(11, 16) || 'Live'}</span>
              </div>
              <h3 className="text-base font-semibold text-white leading-snug mb-4">
                <a href={article.link} target="_blank" rel="noopener noreferrer" className="hover:text-[#3b82f6]">
                  {article.title}
                </a>
              </h3>
              <div className="flex flex-wrap gap-2 mb-2">
                <span className="px-2 py-1 text-[10px] font-bold bg-[#0a0d14] text-[#8b97ab] border border-[#1f2638] rounded">
                  {article.source || 'Source'} · tier {article.tier ?? '—'}
                </span>
              </div>
              <p className="text-xs text-[#8b97ab] mt-auto">{article.nlp_themes || '(awaiting NLP tags)'}</p>
            </div>
          </article>
        ))
      ) : (
        <p className="text-sm text-[#8b97ab] col-span-full">No articles in PostgreSQL yet — run the scrape pipeline, then reload.</p>
      )}
</div>
      </section>
      </Reveal>

      </div>
      
      
      
      
    </>
  )
}
