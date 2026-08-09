import Reveal from '../components/Reveal'
import macroChartImg from '../assets/module-macro.jpg'

export default function MacroDashboard() {
  return (
    <>
      
      
      
      
      <div className="border-b border-white/5 bg-[#0A101C]/50 py-2 overflow-x-auto scrollbar-hide">
      <div className="max-w-[1600px] mx-auto px-6 flex items-center gap-8 text-xs font-medium whitespace-nowrap">
      <div className="flex items-center gap-2">
      <span className="text-gray-500">NIFTY 50:</span>
      <span className="text-white">24,521.38</span>
      <span className="text-[#10B981]">(+142.10)</span>
      </div>
      <div className="flex items-center gap-2">
      <span className="text-gray-500">SENSEX:</span>
      <span className="text-white">79,984.60</span>
      <span className="text-[#10B981]">(+420.30)</span>
      </div>
      <div className="flex items-center gap-2">
      <span className="text-gray-500">INDIA VIX:</span>
      <span className="text-white">15.45</span>
      <span className="text-[#EF4444]">(+2.14%)</span>
      </div>
      <div className="flex items-center gap-2">
      <span className="text-gray-500">USD/INR:</span>
      <span className="text-white">83.82</span>
      <span className="text-[#EF4444]">(-0.09)</span>
      </div>
      <div className="flex items-center gap-2">
      <span className="text-gray-500">BRENT CRUDE:</span>
      <span className="text-white">$78.45</span>
      <span className="text-[#EF4444]">(-1.28)</span>
      </div>
      <div className="flex items-center gap-2">
      <span className="text-gray-500">GOLD (MCX):</span>
      <span className="text-white">...</span>
      </div>
      </div>
      </div>
      
      
      <div className="flex-grow max-w-[1600px] mx-auto w-full px-6 py-8 flex flex-col gap-6">
      
      <Reveal>
      <section className="flex flex-col lg:flex-row gap-8 justify-between items-start">
      <div className="max-w-2xl space-y-3">
      <span className="eyebrow-badge">
      <span className="eyebrow-dot" />
      Live Market Data
      </span>
      <h1 className="text-4xl font-bold text-white mb-2">Indian Macroeconomic Intelligence</h1>
      <p className="text-gray-400">Real-time monitoring of India's financial markets, macroeconomic indicators and economic stability.</p>
      </div>

      <div className="flex gap-4 flex-wrap lg:flex-nowrap w-full lg:w-auto">

      <div className="card-lift glass-panel rounded-xl p-4 flex-1 min-w-[160px]">
      <div className="flex justify-between items-start mb-2">
      <span className="text-xs text-gray-400 font-medium">NIFTY 50</span>
      <span className="text-xs text-[#EF4444] bg-[#EF4444]/10 px-1.5 py-0.5 rounded">-1.25</span>
      </div>
      <div className="text-lg font-bold text-white">24,321.39</div>
      <div className="text-xs text-[#10B981]">(+143.10)</div>
      </div>

      <div className="card-lift glass-panel rounded-xl p-4 flex-1 min-w-[160px]">
      <div className="flex justify-between items-start mb-2">
      <span className="text-xs text-gray-400 font-medium">SENSEX</span>
      <span className="text-xs text-[#10B981] bg-[#10B981]/10 px-1.5 py-0.5 rounded">+0.4%</span>
      </div>
      <div className="text-lg font-bold text-white">79,084.69</div>
      <div className="text-xs text-[#10B981]">(+120.30)</div>
      </div>

      <div className="card-lift glass-panel rounded-xl p-4 flex-1 min-w-[160px]">
      <div className="flex justify-between items-start mb-2">
      <span className="text-xs text-gray-400 font-medium">INDIA VIX</span>
      <span className="text-xs text-[#EF4444] bg-[#EF4444]/10 px-1.5 py-0.5 rounded">+0.01</span>
      </div>
      <div className="text-lg font-bold text-white">13.45</div>
      <div className="text-xs text-[#EF4444]">(+2.14%)</div>
      </div>

      <div className="card-lift glass-panel rounded-xl p-4 flex-1 min-w-[160px]">
      <div className="flex justify-between items-start mb-2">
      <span className="text-xs text-gray-400 font-medium">BRENT CRUDE</span>
      <span className="text-xs text-[#EF4444] bg-[#EF4444]/10 px-1.5 py-0.5 rounded">-1.2%</span>
      </div>
      <div className="text-lg font-bold text-white">$78.45</div>
      </div>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">

      <div className="xl:col-span-2 card-lift glass-panel rounded-xl p-5 flex flex-col">
      <div className="flex justify-between items-center mb-4">
      <div className="flex items-center gap-3">
      <h2 className="text-white font-semibold flex items-center gap-2">
      <svg fill="none" height="16" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="16" xmlns="http://www.w3.org/2000/svg"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                    NIFTY 50 Index Chart
                  </h2>
      <div className="flex bg-[#111827] rounded p-0.5">
      <button className="px-2 py-1 text-xs text-white bg-[#1F2937] rounded shadow">1D</button>
      <button className="px-2 py-1 text-xs text-gray-400 hover:text-white">1W</button>
      <button className="px-2 py-1 text-xs text-gray-400 hover:text-white">1M</button>
      <button className="px-2 py-1 text-xs text-gray-400 hover:text-white">YTD</button>
      </div>
      </div>
      <div className="flex items-center gap-4 text-xs">
      <span className="flex items-center gap-1 text-gray-400"><span className="w-2 h-2 rounded-full bg-[#10B981]"></span> MA(20)</span>
      <span className="flex items-center gap-1 text-gray-400"><span className="w-2 h-2 rounded-full bg-blue-400"></span> MA(50)</span>
      </div>
      </div>
      
      <div className="flex-grow w-full h-[400px] bg-[#0A101C]/50 rounded border border-white/5 relative overflow-hidden flex items-center justify-center bg-cover bg-center" style={{ backgroundImage: `linear-gradient(to top, rgba(6,11,20,0.9), rgba(6,11,20,0.35)), url(${macroChartImg})` }}>
      <span className="text-gray-300 text-sm bg-black/40 backdrop-blur-sm px-3 py-1.5 rounded border border-white/10">Interactive Candlestick Chart Placeholder</span>

      </div>
      </div>
      
      <div className="card-lift glass-panel rounded-xl p-5 flex flex-col gap-6">
      <h2 className="text-white font-semibold">Market Sentiment</h2>
      
      <div className="flex flex-col items-center">
      <div className="flex justify-between w-full text-xs text-gray-400 mb-2">
      <span>FEAR &amp; GREED INDEX</span>
      <span className="text-[#10B981] font-bold">68</span>
      </div>
      
      <div className="relative w-48 h-24 overflow-hidden mb-2">
      <div className="absolute w-48 h-48 rounded-full border-[16px] border-t-[#EF4444] border-l-yellow-500 border-r-[#10B981] border-b-transparent rotate-45"></div>
      <div className="absolute bottom-0 left-1/2 w-1 h-20 bg-gray-300 origin-bottom transform -translate-x-1/2 rotate-45"></div>
      </div>
      <div className="flex justify-between w-full text-xs text-gray-500">
      <span>EXTREME FEAR</span>
      <span>EXTREME GREED</span>
      </div>
      </div>
      
      <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
      <span>RISK APPETITE</span>
      </div>
      <div className="h-1.5 w-full bg-[#111827] rounded-full overflow-hidden">
      <div className="h-full bg-blue-500 w-[70%]"></div>
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
      <span>Low</span>
      <span>High</span>
      </div>
      </div>
      
      <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
      <span>LIQUIDITY</span>
      </div>
      <div className="h-1.5 w-full bg-[#111827] rounded-full overflow-hidden">
      <div className="h-full bg-[#10B981] w-[85%]"></div>
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
      <span>Tight</span>
      <span>Ample</span>
      </div>
      </div>
      
      <div>
      <h3 className="text-xs text-gray-400 mb-3">FII / DII FLOW</h3>
      <div className="flex items-center justify-between gap-2">
      <div className="bg-[#111827]/50 rounded p-2 flex-1">
      <div className="text-[10px] text-gray-500 mb-1">FII</div>
      <div className="text-sm font-semibold text-white flex items-center gap-1">
      <span className="text-[#10B981]">↑</span> ₹1,340 Cr
                    </div>
      </div>
      <div className="bg-[#111827]/50 rounded p-2 flex-1">
      <div className="text-[10px] text-gray-500 mb-1">DII</div>
      <div className="text-sm font-semibold text-white flex items-center gap-1">
      <span className="text-[#10B981]">↑</span> ₹850 Cr
                    </div>
      </div>
      <div className="text-right">
      <div className="text-[#10B981] text-sm font-medium">Net Buy</div>
      </div>
      </div>
      </div>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
      
      <div className="card-lift glass-panel rounded-xl p-5 flex flex-col h-[300px]">
      <div className="flex justify-between items-center mb-4">
      <h2 className="text-white font-semibold text-sm">Sector Treemap</h2>
      <span className="text-[10px] text-gray-500">% CHANGE</span>
      </div>
      
      <div className="flex-grow grid grid-cols-3 grid-rows-3 gap-1 rounded overflow-hidden text-white text-xs font-medium">
      <div className="col-span-2 row-span-2 bg-[#10B981]/80 p-2 flex flex-col justify-center items-center">
      <span>BANKING</span>
      <span className="text-lg">+2.45%</span>
      </div>
      <div className="bg-[#10B981]/60 p-2 flex flex-col justify-center items-center">
      <span>IT</span>
      <span>+0.82%</span>
      </div>
      <div className="bg-[#EF4444]/80 p-2 flex flex-col justify-center items-center">
      <span>PHARMA</span>
      <span>-1.12%</span>
      </div>
      <div className="bg-[#10B981]/70 p-2 flex flex-col justify-center items-center">
      <span>ENERGY</span>
      <span>+1.55%</span>
      </div>
      <div className="bg-[#10B981]/40 p-2 flex flex-col justify-center items-center">
      <span>AUTO</span>
      <span>+0.34%</span>
      </div>
      <div className="bg-gray-700 p-2 flex flex-col justify-center items-center text-[10px]">
      <span>FMCG</span>
      <span>-0.50%</span>
      </div>
      <div className="bg-[#EF4444]/90 p-2 flex flex-col justify-center items-center text-[10px]">
      <span>METALS</span>
      <span>-2.20%</span>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-panel rounded-xl p-5 flex flex-col gap-4 h-[300px]">
      <h2 className="text-white font-semibold text-sm mb-2">Macro Indicators</h2>
      <div className="flex justify-between items-center border-b border-white/5 pb-2">
      <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">GDP GROWTH (YOY)</div>
      <div className="text-lg font-semibold text-white">7.8%</div>
      </div>
      <div className="flex items-center gap-1 text-xs text-[#10B981]">
      <span>↗</span> Above Est.
                </div>
      </div>
      <div className="flex justify-between items-center border-b border-white/5 pb-2">
      <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">CPI INFLATION</div>
      <div className="text-lg font-semibold text-white">4.76%</div>
      </div>
      <div className="flex items-center gap-1 text-xs text-blue-400">
      <span>↘</span> Cooling
                </div>
      </div>
      <div className="flex justify-between items-center border-b border-white/5 pb-2">
      <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">RBI REPO RATE</div>
      <div className="text-lg font-semibold text-white">6.50%</div>
      </div>
      <div className="flex items-center gap-1 text-xs text-gray-400">
      <span>-</span> Unchanged
                </div>
      </div>
      <div className="flex justify-between items-center">
      <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">MANUFACTURING PMI</div>
      <div className="text-lg font-semibold text-white">58.3</div>
      </div>
      <div className="flex items-center gap-1 text-xs text-[#10B981]">
      <span>↗</span> Expansion
                </div>
      </div>
      </div>
      
      <div className="card-lift glass-panel rounded-xl p-5 flex flex-col gap-4 h-[300px]">
      <h2 className="text-white font-semibold text-sm mb-2">Asset Monitor</h2>
      <div className="grid grid-cols-2 gap-4">
      <div className="bg-[#111827]/30 p-3 rounded">
      <div className="text-[10px] text-gray-500 uppercase">EUR / INR</div>
      <div className="text-base font-semibold text-white">91.42</div>
      <div className="text-[10px] text-[#EF4444]">-0.42%</div>
      </div>
      <div className="bg-[#111827]/30 p-3 rounded">
      <div className="text-[10px] text-gray-500 uppercase">GBP / INR</div>
      <div className="text-base font-semibold text-white">108.95</div>
      <div className="text-[10px] text-[#10B981]">+0.22%</div>
      </div>
      <div className="bg-[#111827]/30 p-3 rounded">
      <div className="text-[10px] text-gray-500 uppercase">SILVER (MCX)</div>
      <div className="text-base font-semibold text-white">₹88,240</div>
      <div className="text-[10px] text-[#10B981]">+0.60%</div>
      </div>
      <div className="bg-[#111827]/30 p-3 rounded">
      <div className="text-[10px] text-gray-500 uppercase">NATURAL GAS</div>
      <div className="text-base font-semibold text-white">$2.14</div>
      <div className="text-[10px] text-[#EF4444]">-1.10%</div>
      </div>
      </div>
      </div>
      
      <div className="hidden xl:block"></div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <div className="card-lift glass-panel rounded-xl p-5 flex flex-col">
      <div className="flex items-center gap-2 mb-4">
      <svg className="text-gray-400" fill="none" height="16" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="16" xmlns="http://www.w3.org/2000/svg"><rect height="18" rx="2" ry="2" width="18" x="3" y="4"></rect><line x1="16" x2="16" y1="2" y2="6"></line><line x1="8" x2="8" y1="2" y2="6"></line><line x1="3" x2="21" y1="10" y2="10"></line></svg>
      <h2 className="text-white font-semibold text-sm">Economic Calendar</h2>
      </div>
      <div className="flex flex-col gap-4">
      
      <div className="flex items-center gap-4 p-3 bg-[#111827]/30 rounded-lg">
      <div className="flex flex-col items-center justify-center min-w-[40px]">
      <span className="text-lg font-bold text-white leading-none">12</span>
      <span className="text-[10px] text-gray-500 uppercase">Aug</span>
      </div>
      <div className="flex-grow">
      <div className="text-sm font-medium text-white">CPI Inflation Data Release</div>
      <div className="text-xs text-gray-500">Target: 4.5% | Previous: 4.76%</div>
      </div>
      <div>
      <span className="text-[10px] px-2 py-1 bg-blue-900/50 text-blue-300 rounded border border-blue-800/50">HIGH IMPACT</span>
      </div>
      </div>
      
      <div className="flex items-center gap-4 p-3 bg-[#111827]/30 rounded-lg">
      <div className="flex flex-col items-center justify-center min-w-[40px]">
      <span className="text-lg font-bold text-white leading-none">15</span>
      <span className="text-[10px] text-gray-500 uppercase">Aug</span>
      </div>
      <div className="flex-grow">
      <div className="text-sm font-medium text-white">WPI Inflation Data</div>
      <div className="text-xs text-gray-500">Source: Ministry of Commerce</div>
      </div>
      <div>
      <span className="text-[10px] px-2 py-1 bg-yellow-900/50 text-yellow-300 rounded border border-yellow-800/50">MED IMPACT</span>
      </div>
      </div>
      
      <div className="flex items-center gap-4 p-3 bg-[#111827]/30 rounded-lg">
      <div className="flex flex-col items-center justify-center min-w-[40px]">
      <span className="text-lg font-bold text-white leading-none">28</span>
      <span className="text-[10px] text-gray-500 uppercase">Aug</span>
      </div>
      <div className="flex-grow">
      <div className="text-sm font-medium text-white">RBI MPC Meeting Minutes</div>
      <div className="text-xs text-gray-500">Monetary Policy Insight</div>
      </div>
      <div>
      <span className="text-[10px] px-2 py-1 bg-blue-900/50 text-blue-300 rounded border border-blue-800/50">HIGH IMPACT</span>
      </div>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-panel rounded-xl p-5 flex flex-col border-t-2 border-t-blue-500">
      <div className="flex justify-between items-center mb-4">
      <div className="flex items-center gap-2">
      <svg className="text-blue-400" fill="none" height="16" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="16" xmlns="http://www.w3.org/2000/svg"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
      <h2 className="text-white font-semibold text-sm">AI Macroeconomic Outlook</h2>
      </div>
      <span className="text-[10px] text-[#10B981] bg-[#10B981]/10 px-2 py-1 rounded-full border border-[#10B981]/20">Confidence Score: 88%</span>
      </div>
      <div className="mb-4">
      <h3 className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">STRATEGIC INSIGHTS</h3>
      <p className="text-sm text-gray-300 leading-relaxed border-l-2 border-blue-500 pl-3">
                  Bullish trend remains intact as FII flows stabilize. Technical support for NIFTY identified at 24,150. Resistance at 24,600.
                </p>
      </div>
      <div className="grid grid-cols-2 gap-6 mt-2">
      <div>
      <h3 className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">KEY RISKS</h3>
      <ul className="text-xs text-gray-300 space-y-2">
      <li className="flex items-start gap-2"><span className="text-[#EF4444] mt-0.5">•</span> Global crude price volatility above $85/bbl.</li>
      <li className="flex items-start gap-2"><span className="text-[#EF4444] mt-0.5">•</span> US Federal Reserve interest rate trajectory.</li>
      <li className="flex items-start gap-2"><span className="text-[#EF4444] mt-0.5">•</span> Monsoon distribution across rural belts.</li>
      </ul>
      </div>
      <div>
      <h3 className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">INSTITUTIONAL RECOMMENDATIONS</h3>
      <ul className="text-xs text-gray-300 space-y-2">
      <li className="flex items-start gap-2"><span className="text-[#10B981] mt-0.5">•</span> Overweight: Private Banking &amp; FMCG.</li>
      <li className="flex items-start gap-2"><span className="text-blue-400 mt-0.5">•</span> Neutral: IT Services &amp; Auto.</li>
      <li className="flex items-start gap-2"><span className="text-[#EF4444] mt-0.5">•</span> Underweight: Metal &amp; Smallcap Realty.</li>
      </ul>
      </div>
      </div>
      </div>
      </section>
      </Reveal>
      </div>


      
      
    </>
  )
}
