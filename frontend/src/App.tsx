import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import AccuracyDashboard from './pages/AccuracyDashboard'
import NewsDashboard from './pages/NewsDashboard'
import MacroDashboard from './pages/MacroDashboard'
import TradeCorridorDashboard from './pages/TradeCorridorDashboard'
import PortfolioDashboard from './pages/PortfolioDashboard'

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/news" element={<NewsDashboard />} />
          <Route path="/macroeconomics" element={<MacroDashboard />} />
          <Route path="/trade-corridor" element={<TradeCorridorDashboard />} />
          <Route path="/portfolio-exposure" element={<PortfolioDashboard />} />
          <Route path="/quality" element={<AccuracyDashboard />} />
          <Route path="/about" element={<Navigate to="/quality" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
