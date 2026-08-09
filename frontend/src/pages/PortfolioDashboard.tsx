import Reveal from '../components/Reveal'

export default function PortfolioDashboard() {
  return (
    <div className="px-margin-page max-w-container-max mx-auto py-8 space-y-6">

      <Reveal>
      <header className="glass-card p-6">
      <span className="eyebrow-badge mb-3 inline-flex">
      <span className="eyebrow-dot" />
      Live Portfolio Analytics
      </span>
      <h1 className="text-xl text-white font-semibold mb-2">Portfolio Exposure &amp; GPR Analytics</h1>
      <p className="text-gray-400 max-w-3xl mb-6">Understand how geopolitical events impact investment portfolios, sector exposure and asset allocation. Real-time monitoring of systemic risk across global markets.</p>
      <div className="flex gap-8">
      <div>
      <div className="text-xs text-gray-500 font-semibold tracking-wider uppercase mb-1">Market Status</div>
      <div className="flex items-center gap-2 text-[#10b981] font-medium">
      <div className="w-2 h-2 rounded-full bg-[#10b981]"></div>
                Live Monitoring Active
              </div>
      </div>
      <div>
      <div className="text-xs text-gray-500 font-semibold tracking-wider uppercase mb-1">Last Update</div>
      <div className="text-white font-medium">02:45 PM IST</div>
      </div>
      </div>
      </header>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-4 gap-6">
      <div className="card-lift glass-card p-5 relative overflow-hidden">
      <div className="text-xs text-gray-500 font-semibold tracking-wider uppercase mb-2">Portfolio Risk Score</div>
      <div className="text-3xl text-white font-bold mb-2">64/100</div>
      <div className="text-[#ef4444] text-xs font-medium flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
              +4.2% from prev. week
            </div>
      <div className="absolute top-4 right-4 text-[#ef4444] opacity-80"><svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path clipRule="evenodd" d="M10 1.944A11.954 11.954 0 012.166 5C2.056 5.649 2 6.319 2 7c0 5.225 3.34 9.67 8 11.317C14.66 16.67 18 12.225 18 7c0-.682-.057-1.35-.166-1.998A11.954 11.954 0 0110 1.944zM11 14a1 1 0 11-2 0 1 1 0 012 0zm0-7a1 1 0 10-2 0v3a1 1 0 102 0V7z" fillRule="evenodd"></path></svg></div>
      </div>
      <div className="card-lift glass-card p-5 relative">
      <div className="text-xs text-gray-500 font-semibold tracking-wider uppercase mb-2">India GPR Index</div>
      <div className="text-3xl text-white font-bold mb-2">112.4</div>
      <div className="text-[#10b981] text-xs font-medium flex items-center gap-1">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
              -1.8% Stability Improving
            </div>
      <div className="absolute top-4 right-4 text-[#3b82f6] opacity-80"><svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path clipRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM4.332 8.027a6.012 6.012 0 011.912-2.706C6.512 5.73 6.974 6 7.5 6A1.5 1.5 0 019 7.5V8a2 2 0 004 0 2 2 0 011.523-1.943A5.977 5.977 0 0116 10c0 .34-.028.675-.083 1H15a2 2 0 00-2 2v2.197A5.973 5.973 0 0110 16v-2a2 2 0 00-2-2 2 2 0 01-2-2 2 2 0 00-1.668-1.973z" fillRule="evenodd"></path></svg></div>
      </div>
      <div className="card-lift glass-card p-5 relative">
      <div className="text-xs text-gray-500 font-semibold tracking-wider uppercase mb-2">Expected Portfolio Impact</div>
      <div className="text-3xl text-white font-bold mb-2">-$1.2M</div>
      <div className="text-gray-400 text-xs font-medium">
              Based on current volatility
            </div>
      <div className="absolute top-4 right-4 text-[#f59e0b] opacity-80"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg></div>
      </div>
      <div className="card-lift glass-card p-5 relative border-l-4 border-l-[#10b981]">
      <div className="text-xs text-gray-500 font-semibold tracking-wider uppercase mb-2">Recommended Allocation</div>
      <div className="text-3xl text-white font-bold mb-2">OPTIMAL</div>
      <div className="text-[#10b981] text-xs font-medium">
              No rebalancing required
            </div>
      <div className="absolute top-4 right-4 text-[#10b981] opacity-80"><svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path clipRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" fillRule="evenodd"></path></svg></div>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-12 gap-6">

      <div className="card-lift glass-card p-5 col-span-3 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-6">Portfolio Allocation</h2>
      <div className="flex-grow flex flex-col items-center justify-center relative mb-6">
      <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 100 100">
      <circle cx="50" cy="50" fill="transparent" r="40" stroke="#1f2937" strokeWidth="12"></circle>
      
      <circle cx="50" cy="50" fill="transparent" r="40" stroke="#3b82f6" strokeDasharray="251.2" strokeDashoffset="138.16" strokeWidth="12"></circle>
      
      <circle cx="50" cy="50" fill="transparent" r="40" stroke="#10b981" strokeDasharray="251.2" strokeDashoffset="220" strokeWidth="12" transform="rotate(162 50 50)"></circle>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
      <span className="text-white font-bold text-lg">Total</span>
      <span className="text-gray-400 text-xs">$42.8B</span>
      </div>
      </div>
      <div className="flex flex-col gap-3">
      <div className="flex justify-between items-center text-xs">
      <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-[#3b82f6]"></div><span className="text-gray-300">Tech</span></div>
      <span className="text-white font-medium">45%</span>
      </div>
      <div className="flex justify-between items-center text-xs">
      <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-[#10b981]"></div><span className="text-gray-300">Financials</span></div>
      <span className="text-white font-medium">25%</span>
      </div>
      <div className="flex justify-between items-center text-xs">
      <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-indigo-500"></div><span className="text-gray-300">Energy</span></div>
      <span className="text-white font-medium">15%</span>
      </div>
      <div className="flex justify-between items-center text-xs">
      <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gray-500"></div><span className="text-gray-300">Healthcare</span></div>
      <span className="text-white font-medium">15%</span>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-card p-5 col-span-6 flex flex-col">
      <div className="flex justify-between items-center mb-6">
      <h2 className="text-base font-semibold text-white">Historical India GPR Index</h2>
      <div className="flex gap-1 bg-[#0f131f] rounded p-1">
      <button className="px-2 py-1 text-xs rounded bg-gray-700 text-white">2d</button>
      <button className="px-2 py-1 text-xs rounded text-gray-400 hover:text-white">6m</button>
      <button className="px-2 py-1 text-xs rounded text-gray-400 hover:text-white">1y</button>
      </div>
      </div>
      <div className="flex-grow w-full relative min-h-[200px]">
      <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 400 150">
      <path d="M 0 100 Q 50 120 100 80 T 200 120 T 300 50 T 400 30" fill="none" stroke="#60a5fa" strokeWidth="3"></path>
      <circle cx="200" cy="120" fill="#f59e0b" r="4"></circle>
      </svg>
      <div className="absolute bottom-6 left-[48%] text-[#f59e0b] text-xs transform -translate-x-1/2 bg-[#0f131f]/80 px-2 py-1 rounded border border-white/10">
              Border Tensions
            </div>
      <div className="absolute bottom-0 w-full flex justify-between text-[10px] text-gray-500 px-2 border-t border-white/5 pt-2 mt-4">
      <span>OCT</span><span>NOV</span><span>DEC</span><span>JAN</span><span>FEB</span><span>MAR</span>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-card p-5 col-span-3 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-6">Risk Analytics</h2>
      <div className="flex flex-col gap-5">
      <div>
      <div className="flex justify-between text-xs mb-2">
      <span className="text-gray-300">Overall Risk</span>
      <span className="text-white font-medium">64%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5">
      <div className="bg-[#ef4444] h-1.5 rounded-full" style={{width: '64%'}}></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between text-xs mb-2">
      <span className="text-gray-300">Market Stress</span>
      <span className="text-white font-medium">42%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5">
      <div className="bg-indigo-400 h-1.5 rounded-full" style={{width: '42%'}}></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between text-xs mb-2">
      <span className="text-gray-300">Volatility Index</span>
      <span className="text-white font-medium">18.4</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5">
      <div className="bg-gray-400 h-1.5 rounded-full" style={{width: '30%'}}></div>
      </div>
      </div>
      <div>
      <div className="flex justify-between text-xs mb-2">
      <span className="text-gray-300">Diversification</span>
      <span className="text-white font-medium">High</span>
      </div>
      <div className="flex gap-1 h-1.5 w-full">
      <div className="bg-[#10b981] rounded-full flex-1"></div>
      <div className="bg-[#10b981] rounded-full flex-1"></div>
      <div className="bg-[#10b981] rounded-full flex-1"></div>
      <div className="bg-gray-700 rounded-full flex-1"></div>
      </div>
      </div>
      </div>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-12 gap-6">

      <div className="card-lift glass-card p-5 col-span-3 flex flex-col">
      <div className="flex justify-between items-center mb-4">
      <h2 className="text-base font-semibold text-white">Sector Exposure</h2>
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">Institutional View</span>
      </div>
      <div className="grid grid-cols-2 grid-rows-3 gap-2 flex-grow">
      <div className="row-span-2 col-span-1 bg-[#15201c] border border-[#10b981]/20 rounded flex flex-col items-center justify-center p-3">
      <span className="text-white font-bold text-lg">TECH</span>
      <span className="text-[#10b981] text-xs">+3.4%</span>
      </div>
      <div className="col-span-1 bg-[#201515] border border-[#ef4444]/20 rounded flex flex-col items-center justify-center p-3">
      <span className="text-white font-bold text-sm">BANKING</span>
      <span className="text-[#ef4444] text-xs">-1.2%</span>
      </div>
      <div className="flex gap-2 col-span-1">
      <div className="flex-1 bg-gray-800/50 border border-white/5 rounded flex flex-col items-center justify-center p-2">
      <span className="text-white font-bold text-[10px]">AUTO</span>
      <span className="text-gray-400 text-[10px]">+0.5%</span>
      </div>
      <div className="flex-1 bg-gray-800/50 border border-white/5 rounded flex flex-col items-center justify-center p-2">
      <span className="text-white font-bold text-[10px]">PHARMA</span>
      <span className="text-gray-400 text-[10px]">-0.4%</span>
      </div>
      </div>
      <div className="col-span-2 bg-[#172033] border border-[#3b82f6]/20 rounded flex flex-col items-center justify-center p-3">
      <span className="text-white font-bold text-sm">ENERGY</span>
      <span className="text-[#3b82f6] text-xs">+2.1%</span>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-card p-5 col-span-6 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-4">Scenario Analysis</h2>
      <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
      <thead>
      <tr className="text-[10px] text-gray-500 uppercase tracking-wider border-b border-white/10">
      <th className="pb-3 font-medium">Scenario</th>
      <th className="pb-3 font-medium text-right pr-4">Prob.</th>
      <th className="pb-3 font-medium">Impact</th>
      <th className="pb-3 font-medium text-right">Action</th>
      </tr>
      </thead>
      <tbody className="text-sm divide-y divide-white/5">
      <tr>
      <td className="py-3 text-gray-200">Red Sea Escalation</td>
      <td className="py-3 text-right pr-4 text-white">35%</td>
      <td className="py-3 text-[#ef4444] font-medium">Severe</td>
      <td className="py-3 text-right"><span className="px-2 py-1 bg-gray-800 text-gray-300 text-xs rounded border border-gray-700">HEDGE OIL</span></td>
      </tr>
      <tr>
      <td className="py-3 text-gray-200">Oil Price Shock</td>
      <td className="py-3 text-right pr-4 text-white">20%</td>
      <td className="py-3 text-[#f59e0b] font-medium">Moderate</td>
      <td className="py-3 text-right"><span className="px-2 py-1 bg-gray-800 text-gray-300 text-xs rounded border border-gray-700">REALLOCATE</span></td>
      </tr>
      <tr>
      <td className="py-3 text-gray-200">China Trade Restrictions</td>
      <td className="py-3 text-right pr-4 text-white">15%</td>
      <td className="py-3 text-[#f59e0b] font-medium">Medium</td>
      <td className="py-3 text-right"><span className="px-2 py-1 bg-gray-800 text-gray-300 text-xs rounded border border-gray-700">WATCH</span></td>
      </tr>
      <tr>
      <td className="py-3 text-gray-200">USD-INR Volatility</td>
      <td className="py-3 text-right pr-4 text-white">65%</td>
      <td className="py-3 text-[#f59e0b] font-medium">Moderate</td>
      <td className="py-3 text-right"><span className="px-2 py-1 bg-gray-800 text-gray-300 text-xs rounded border border-gray-700">HEDGE CURR</span></td>
      </tr>
      </tbody>
      </table>
      </div>
      </div>
      
      <div className="card-lift glass-card p-5 col-span-3 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-4">Risk Alerts</h2>
      <div className="flex flex-col gap-3 flex-grow">
      <div className="glass-card-inner p-3 border-l-2 border-l-[#ef4444]">
      <div className="flex justify-between items-center mb-1">
      <span className="text-[10px] font-bold text-[#ef4444] tracking-wider uppercase">Critical</span>
      <span className="text-[10px] text-gray-500">2hr ago</span>
      </div>
      <p className="text-xs text-gray-300 leading-snug">High China dependency in Tech sector. Recommend immediate diversification.</p>
      </div>
      <div className="glass-card-inner p-3 border-l-2 border-l-[#f59e0b]">
      <div className="flex justify-between items-center mb-1">
      <span className="text-[10px] font-bold text-[#f59e0b] tracking-wider uppercase">Moderate</span>
      <span className="text-[10px] text-gray-500">5hr ago</span>
      </div>
      <p className="text-xs text-gray-300 leading-snug">Currency fluctuation exceeding 3% threshold. Automated hedges activated.</p>
      </div>
      </div>
      <button className="mt-4 text-xs text-[#3b82f6] hover:text-white transition-colors text-center w-full">View All 12 Alerts</button>
      </div>
      </section>
      </Reveal>

      <Reveal>
      <section className="grid grid-cols-12 gap-6">

      <div className="card-lift glass-card p-5 col-span-4 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-4">Historical Performance vs. GPR</h2>
      <div className="flex items-center gap-4 mb-4 text-xs">
      <div className="flex items-center gap-2"><div className="w-3 h-1 bg-[#3b82f6]"></div><span className="text-gray-300">Portfolio Return</span></div>
      <div className="flex items-center gap-2"><div className="w-3 h-1 bg-[#f59e0b]"></div><span className="text-gray-300">India GPR Index</span></div>
      </div>
      <div className="flex-grow w-full relative min-h-[220px]">
      <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 300 200">
      
      <line stroke="#1f2937" strokeWidth="1" x1="0" x2="300" y1="20" y2="20"></line>
      <line stroke="#1f2937" strokeWidth="1" x1="0" x2="300" y1="60" y2="60"></line>
      <line stroke="#1f2937" strokeWidth="1" x1="0" x2="300" y1="100" y2="100"></line>
      <line stroke="#1f2937" strokeWidth="1" x1="0" x2="300" y1="140" y2="140"></line>
      <line stroke="#1f2937" strokeWidth="1" x1="0" x2="300" y1="180" y2="180"></line>
      
      <text fill="#6b7280" fontSize="10" x="0" y="25">15%</text>
      <text fill="#6b7280" fontSize="10" x="0" y="65">10%</text>
      <text fill="#6b7280" fontSize="10" x="0" y="105">5%</text>
      <text fill="#6b7280" fontSize="10" x="0" y="145">0%</text>
      <text fill="#6b7280" fontSize="10" x="0" y="185">-5%</text>
      
      <path d="M 30 160 L 60 140 L 90 150 L 120 110 L 150 120 L 180 80 L 210 50 L 240 100 L 270 40 L 300 70" fill="none" stroke="#3b82f6" strokeWidth="2"></path>
      <path d="M 30 180 L 60 170 L 90 175 L 120 150 L 150 160 L 180 130 L 210 70 L 240 140 L 270 90 L 300 120" fill="none" stroke="#f59e0b" strokeWidth="2"></path>
      </svg>
      <div className="absolute bottom-0 w-full flex justify-between text-[8px] text-gray-500 pl-8 pr-2 pt-1 transform -rotate-45 origin-bottom-left">
      <span>Apr '23</span><span>May '23</span><span>Jun '23</span><span>Jul '23</span><span>Aug '23</span><span>Sep '23</span><span>Oct '23</span><span>Nov '23</span><span>Dec '23</span><span>Jan '24</span><span>Feb '24</span><span>Mar '24</span>
      </div>
      </div>
      </div>
      
      <div className="card-lift glass-card p-5 col-span-4 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-4">Top Asset Exposures</h2>
      <div className="overflow-x-auto flex-grow">
      <table className="w-full text-left border-collapse">
      <thead>
      <tr className="text-[10px] text-gray-500 uppercase tracking-wider border-b border-white/10">
      <th className="pb-3 font-medium">Asset</th>
      <th className="pb-3 font-medium text-right pr-4">Risk Contribution</th>
      <th className="pb-3 font-medium text-right">Weighted Impact</th>
      </tr>
      </thead>
      <tbody className="text-sm divide-y divide-white/5">
      <tr>
      <td className="py-3 flex items-center gap-2">
      <div className="w-6 h-6 rounded bg-blue-900/50 flex items-center justify-center text-xs text-blue-400 font-bold">R</div>
      <span className="text-gray-200 text-xs font-medium">RELIANCE</span>
      </td>
      <td className="py-3 text-right pr-4 text-white text-xs">35%</td>
      <td className="py-3 text-right">
      <div className="flex items-center justify-end gap-2">
      <span className="text-xs text-gray-300">22%</span>
      <div className="w-8 h-1.5 bg-[#3b82f6] rounded"></div>
      </div>
      </td>
      </tr>
      <tr>
      <td className="py-3 flex items-center gap-2">
      <div className="w-6 h-6 rounded bg-red-900/50 flex items-center justify-center text-xs text-red-400 font-bold">H</div>
      <span className="text-gray-200 text-xs font-medium">HDFC BANK</span>
      </td>
      <td className="py-3 text-right pr-4 text-white text-xs">22%</td>
      <td className="py-3 text-right">
      <div className="flex items-center justify-end gap-2">
      <span className="text-xs text-gray-300">17%</span>
      <div className="w-6 h-1.5 bg-[#f59e0b] rounded"></div>
      </div>
      </td>
      </tr>
      <tr>
      <td className="py-3 flex items-center gap-2">
      <div className="w-6 h-6 rounded bg-indigo-900/50 flex items-center justify-center text-xs text-indigo-400 font-bold">I</div>
      <span className="text-gray-200 text-xs font-medium">INFOSYS</span>
      </td>
      <td className="py-3 text-right pr-4 text-white text-xs">1.5%</td>
      <td className="py-3 text-right">
      <div className="flex items-center justify-end gap-2">
      <span className="text-xs text-gray-300">10%</span>
      <div className="w-4 h-1.5 bg-[#f59e0b] rounded"></div>
      </div>
      </td>
      </tr>
      <tr>
      <td className="py-3 flex items-center gap-2">
      <div className="w-6 h-6 rounded bg-gray-700 flex items-center justify-center text-xs text-white font-bold">T</div>
      <span className="text-gray-200 text-xs font-medium">TCS</span>
      </td>
      <td className="py-3 text-right pr-4 text-white text-xs">1.2%</td>
      <td className="py-3 text-right">
      <div className="flex items-center justify-end gap-2">
      <span className="text-xs text-gray-300">8%</span>
      <div className="w-3 h-1.5 bg-[#ef4444] rounded"></div>
      </div>
      </td>
      </tr>
      <tr>
      <td className="py-3 flex items-center gap-2">
      <div className="w-6 h-6 rounded bg-yellow-900/50 flex items-center justify-center text-xs text-yellow-500 font-bold">L</div>
      <span className="text-gray-200 text-xs font-medium">L&amp;T</span>
      </td>
      <td className="py-3 text-right pr-4 text-white text-xs">1.2%</td>
      <td className="py-3 text-right">
      <div className="flex items-center justify-end gap-2">
      <span className="text-xs text-gray-300">6%</span>
      <div className="w-2 h-1.5 bg-[#f59e0b] rounded"></div>
      </div>
      </td>
      </tr>
      </tbody>
      </table>
      </div>
      </div>
      
      <div className="card-lift glass-card p-5 col-span-4 flex flex-col">
      <h2 className="text-base font-semibold text-white mb-4">Recommended Actions</h2>
      <div className="flex flex-col gap-3 flex-grow">
      <div className="glass-card-inner p-3 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors group">
      <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-[#10b981]/20 text-[#10b981] flex items-center justify-center">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 6v6m0 0v6m0-6h6m-6 0H6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
      </div>
      <div>
      <div className="text-sm text-white font-medium">Increase Healthcare</div>
      <div className="text-xs text-gray-400">Defensive pivot +4%</div>
      </div>
      </div>
      <svg className="w-4 h-4 text-gray-500 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
      </div>
      <div className="glass-card-inner p-3 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors group">
      <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-gray-700 text-gray-300 flex items-center justify-center">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
      </div>
      <div>
      <div className="text-sm text-white font-medium">Hedge USD-INR</div>
      <div className="text-xs text-gray-400">Options expiry June 24</div>
      </div>
      </div>
      <svg className="w-4 h-4 text-gray-500 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
      </div>
      <div className="glass-card-inner p-3 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors group">
      <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-[#ef4444]/20 text-[#ef4444] flex items-center justify-center">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M20 12H4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
      </div>
      <div>
      <div className="text-sm text-white font-medium">Trim Metal Exposure</div>
      <div className="text-xs text-gray-400">China demand slowdown</div>
      </div>
      </div>
      <svg className="w-4 h-4 text-gray-500 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
      </div>
      </div>
      <button className="btn-primary mt-4 w-full text-white py-2.5 rounded-lg text-sm font-semibold">
            Execute All Optimizations
          </button>
      </div>
      </section>
      </Reveal>

    </div>
  )
}
