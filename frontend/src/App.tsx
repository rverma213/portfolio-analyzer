import { NavLink, Route, Routes } from 'react-router-dom'
import { CompanyDrawer } from './components/CompanyDrawer'
import { Backtest } from './pages/Backtest'
import { Overview } from './pages/Overview'
import { Portfolio } from './pages/Portfolio'
import { Screener } from './pages/Screener'
import { Universe } from './pages/Universe'
import { useApp } from './state'

const STEPS = [
  { to: '/', label: 'Overview', n: '' },
  { to: '/universe', label: 'Universe', n: '1' },
  { to: '/screener', label: 'Screener', n: '2' },
  { to: '/portfolio', label: 'Portfolio', n: '3' },
  { to: '/backtest', label: 'Backtest', n: '4' },
]

export default function App() {
  const { meta, asOf, setAsOf } = useApp()
  const dates = [...meta.as_of_dates].reverse()
  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">
          <div className="brand-mark">PA</div>
          <div>
            <div className="brand-title">Portfolio Analyzer</div>
            <div className="brand-sub">Global smaller companies</div>
          </div>
        </div>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.to}>
              <NavLink to={s.to} end={s.to === '/'} className={({ isActive }) => `step ${isActive ? 'active' : ''}`}>
                <span className="step-n">{s.n || '◎'}</span>{s.label}
              </NavLink>
            </li>
          ))}
        </ol>
        <div className="sidebar-foot">
          <label className="field">
            <span className="field-label">As of</span>
            <select value={asOf} onChange={(e) => setAsOf(e.target.value)}>
              {dates.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <div className="muted small">
            Data: {meta.dataset.source} · {meta.dataset.companies.toLocaleString()} companies<br />
            {meta.dataset.first_month.slice(0, 7)} → {meta.dataset.last_month.slice(0, 7)}
          </div>
        </div>
      </nav>
      <main className="main">
        {meta.data_report && (
          <details className="demo-banner real">
            <summary>
              <strong>Real data</strong> · holdings as of {meta.data_report.holdings_as_of} ·{' '}
              {meta.data_report.resolved.toLocaleString()} of {meta.data_report.holdings.toLocaleString()} constituents priced ·{' '}
              {meta.data_report.statements_from_sec} with SEC filings, {meta.data_report.statements_from_yahoo} from Yahoo ·{' '}
              {meta.data_report.with_5y_history} with 5+ years of statements. <span className="muted">Known limitations ▾</span>
            </summary>
            <ul>{meta.data_report.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
          </details>
        )}
        {meta.demo && (
          <div className="demo-banner">
            <strong>Demo data.</strong> Synthetic companies built to exercise every step of the process. Results show how the
            machinery works, not whether the strategy works.
          </div>
        )}
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/universe" element={<Universe />} />
          <Route path="/screener" element={<Screener />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/backtest" element={<Backtest />} />
        </Routes>
      </main>
      <CompanyDrawer />
    </div>
  )
}
