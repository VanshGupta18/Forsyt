// App.tsx wires up the app's ROUTES — i.e. it maps URL paths (like "/news")
// to the React component that should be shown for that path. This is called
// "client-side routing": react-router-dom watches the browser's URL (using
// the normal browser History API) and swaps which component is rendered,
// entirely in JavaScript, without ever asking the server for a new HTML page.
// That's what makes clicking between pages feel instant instead of a full
// browser reload.
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import AccuracyDashboard from './pages/AccuracyDashboard'
import NewsDashboard from './pages/NewsDashboard'
import MacroDashboard from './pages/MacroDashboard'
import CorridorRiskDashboard from './pages/CorridorRiskDashboard'
import PortfolioDashboard from './pages/PortfolioDashboard'

function App() {
  return (
    // BrowserRouter reads the current URL and makes routing info available
    // (via React Context) to every component nested inside it — including
    // the <Routes> below and any component that calls hooks like
    // useLocation()/useSearchParams() (AppChrome and several pages do).
    <BrowserRouter>
      {/* Layout wraps EVERY page with the shared header (AppChrome), the
          page content in the middle, and the footer — see Layout.tsx. */}
      <Layout>
        {/* <Routes> looks at the current URL and renders the `element` of the
            first <Route> below whose `path` matches. Only one page is ever
            shown at a time — this is the whole app's site map. */}
        <Routes>
          {/* "/" — Home: a hero "today's verdict" banner with a spinning globe,
              followed by a grid of links into the other modules. */}
          <Route path="/" element={<Home />} />
          {/* "/news" — News Intelligence: filterable feed of geopolitical headlines. */}
          <Route path="/news" element={<NewsDashboard />} />
          {/* "/macroeconomics" — Indian Market Stress Monitor: combines the
              news-risk score with NIFTY market volatility into one verdict. */}
          <Route path="/macroeconomics" element={<MacroDashboard />} />
          {/* "/trade-corridor" — Trade & Corridor Risk: interactive world map
              of shipping lanes / border crossings and their risk levels. */}
          <Route path="/trade-corridor" element={<CorridorRiskDashboard />} />
          {/* "/portfolio-exposure" — Portfolio Exposure & GPR Analytics:
              illustrative sector-sensitivity view driven by the live regime. */}
          <Route path="/portfolio-exposure" element={<PortfolioDashboard />} />
          {/* "/quality" — Platform Quality & Accuracy: validation/health
              dashboard answering "can you trust these numbers?". */}
          <Route path="/quality" element={<AccuracyDashboard />} />
          {/* "/about" has no page component of its own — <Navigate replace>
              immediately redirects the browser to "/quality" instead.
              `replace` means "/about" doesn't linger in back-button history. */}
          <Route path="/about" element={<Navigate to="/quality" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
