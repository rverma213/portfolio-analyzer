import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from './api'
import type { BacktestParams, Meta, PortfolioParams, ScreenParams } from './types'

// One as-of date and one set of parameters shared by every stage, so a change
// in the screener flows through to the portfolio and the backtest.
type AppState = {
  meta: Meta
  asOf: string
  setAsOf: (d: string) => void
  screen: ScreenParams
  setScreen: (p: ScreenParams) => void
  portfolio: PortfolioParams
  setPortfolio: (p: PortfolioParams) => void
  backtest: BacktestParams
  setBacktest: (p: BacktestParams) => void
  resetParams: () => void
  company: string | null
  openCompany: (id: string | null) => void
}

const Ctx = createContext<AppState | null>(null)

function stored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback
  } catch {
    return fallback
  }
}

function persist(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch { /* storage unavailable: settings last for this session only */ }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [asOf, setAsOf] = useState('')
  const [screen, setScreenState] = useState<ScreenParams | null>(null)
  const [portfolio, setPortfolioState] = useState<PortfolioParams | null>(null)
  const [backtest, setBacktestState] = useState<BacktestParams | null>(null)
  // The open company is mirrored in the URL hash (#company=ID) so a view can be shared.
  const [company, setCompany] = useState<string | null>(
    () => new URLSearchParams(window.location.hash.slice(1)).get('company'))
  const openCompany = useCallback((id: string | null) => {
    setCompany(id)
    const url = window.location.pathname + window.location.search + (id ? `#company=${encodeURIComponent(id)}` : '')
    window.history.replaceState(window.history.state, '', url)
  }, [])

  useEffect(() => {
    api.meta()
      .then((m) => {
        setMeta(m)
        setAsOf(m.latest)
        setScreenState(stored('specb.screen', m.defaults.screen))
        setPortfolioState(stored('specb.portfolio', m.defaults.portfolio))
        setBacktestState(stored('specb.backtest', m.defaults.backtest))
      })
      .catch((e) => setError(String(e.message ?? e)))
  }, [])

  const setScreen = useCallback((p: ScreenParams) => { setScreenState(p); persist('specb.screen', p) }, [])
  const setPortfolio = useCallback((p: PortfolioParams) => { setPortfolioState(p); persist('specb.portfolio', p) }, [])
  const setBacktest = useCallback((p: BacktestParams) => { setBacktestState(p); persist('specb.backtest', p) }, [])
  const resetParams = useCallback(() => {
    if (!meta) return
    setScreen(meta.defaults.screen)
    setPortfolio(meta.defaults.portfolio)
    setBacktest(meta.defaults.backtest)
  }, [meta, setScreen, setPortfolio, setBacktest])

  if (error) {
    return (
      <div className="fatal">
        <h1>Cannot reach the API</h1>
        <p>{error}</p>
        <p>Start the backend first:</p>
        <pre>cd backend{'\n'}python -m smallcap.cli build-demo{'\n'}python -m smallcap.cli serve</pre>
      </div>
    )
  }
  if (!meta || !screen || !portfolio || !backtest) return <div className="fatal muted">Loading…</div>

  return (
    <Ctx.Provider value={{
      meta, asOf, setAsOf, screen, setScreen, portfolio, setPortfolio, backtest, setBacktest, resetParams,
      company, openCompany,
    }}>
      {children}
    </Ctx.Provider>
  )
}

export function useApp() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp outside AppProvider')
  return v
}

// Load data when inputs change; keeps the previous result while reloading.
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)
  const run = useCallback(() => {
    const id = ++seq.current
    setLoading(true)
    setError(null)
    fn()
      .then((d) => { if (id === seq.current) setData(d) })
      .catch((e) => { if (id === seq.current) setError(String(e.message ?? e)) })
      .finally(() => { if (id === seq.current) setLoading(false) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { data, error, loading, reload: run }
}
