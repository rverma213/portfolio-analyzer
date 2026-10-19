import type {
  BacktestParams, BacktestResponse, CompanyResponse, Meta, Pipeline, PortfolioParams,
  PortfolioResponse, ScreenParams, ScreenResponse, StockOption, StockResponse, Universe,
} from './types'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch { /* not JSON */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const q = (asOf?: string | null) => (asOf ? `?as_of=${asOf}` : '')
const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  meta: () => call<Meta>('/api/meta'),
  pipeline: (asOf?: string | null) => call<Pipeline>(`/api/pipeline${q(asOf)}`),
  universe: (asOf?: string | null) => call<Universe>(`/api/universe${q(asOf)}`),
  screen: (asOf: string | null, screen: ScreenParams) =>
    call<ScreenResponse>('/api/screen', post({ as_of: asOf, screen })),
  company: (id: string, asOf?: string | null) =>
    call<CompanyResponse>(`/api/company/${encodeURIComponent(id)}${q(asOf)}`),
  stocks: () => call<StockOption[]>('/api/stocks'),
  stock: (id: string, asOf?: string | null) =>
    call<StockResponse>(`/api/stock/${encodeURIComponent(id)}${q(asOf)}`),
  portfolio: (asOf: string | null, screen: ScreenParams, portfolio: PortfolioParams) =>
    call<PortfolioResponse>('/api/portfolio', post({ as_of: asOf, screen, portfolio })),
  backtest: (screen: ScreenParams, portfolio: PortfolioParams, backtest: BacktestParams, refresh = false) =>
    call<BacktestResponse>('/api/backtest', post({ screen, portfolio, backtest, refresh })),
}
