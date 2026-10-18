// Shapes returned by the FastAPI backend (backend/smallcap/api.py).

export type ScreenParams = {
  min_adv_usd: number
  min_years: number
  min_years_estimated: number
  min_positive_fcf_years: number
  max_net_debt_ebitda: number
  require_roe_above_coe: boolean
  max_dilution: number
  max_receivables_gap: number
  allow_off_benchmark: boolean
  cost_of_equity: Record<string, number>
  pillar_weights: Record<string, number>
  research_list_size: number
  min_group_size: number
}

export type PortfolioParams = {
  aum_usd: number
  target_holdings: number
  min_holdings: number
  max_holdings: number
  conviction_weights: Record<string, number>
  max_position: number
  sector_band: number
  country_band: number
  country_band_large: number
  large_countries: string[]
  adv_days: number
  adv_participation: number
  max_cash: number
  off_benchmark_max: number
  sell_rank_pct: number
  trade_band: number
  max_governance_flags: number
  include_financials: boolean
}

export type BacktestParams = {
  start: string
  end: string | null
  rebalance_months: number
  cost_bps: number
  quintile_min_names: number
}

export type DataReport = {
  holdings_as_of: string | null
  holdings: number
  resolved: number
  unresolved: number
  unresolved_weight: number
  with_statements: number
  statements_from_sec: number
  statements_from_yahoo: number
  with_5y_history: number
  weight_with_5y_history: number
  short_price_history: string[]
  no_statements: string[]
  limitations: string[]
}

export type MetricDef = { key: string; label: string; pillar: string; higher_is_better: boolean }

export type Meta = {
  dataset: { source: string; built: string; companies: number; statements: number; first_month: string; last_month: string }
  demo: boolean
  data_report: DataReport | null
  as_of_dates: string[]
  latest: string
  defaults: { screen: ScreenParams; portfolio: PortfolioParams; backtest: BacktestParams }
  metrics: MetricDef[]
  pillars: string[]
  filters: { key: string; label: string; applies_to_financials: boolean }[]
}

export type FunnelStep = { key: string; label: string; remaining: number; removed: number }

export type Row = Record<string, any>

export type Pipeline = {
  as_of: string
  stages: { key: string; label: string; count: number | null; detail: string }[]
  funnel: FunnelStep[]
}

export type Universe = {
  as_of: string
  summary: { companies: number; benchmark: number; median_mcap: number; total_mcap: number }
  by_country: Row[]
  by_sector: Row[]
  by_region: Row[]
  rows: Row[]
}

export type ScreenResponse = {
  as_of: string
  funnel: FunnelStep[]
  passed: Row[]
  excluded: Row[]
  financials: Row[]
}

export type CompanyResponse = {
  as_of: string
  company: Row
  screen: Row | null
  history: Row[]
  prices: Row[]
}

export type Check = { rule: string; limit: string; actual: string | number; pass: boolean; advisory?: boolean }
export type Exposure = { name: string; portfolio: number; benchmark: number; active: number; min: number; max: number; within: boolean; below_floor: boolean }

export type PortfolioResponse = {
  as_of: string
  holdings: Row[]
  checks: Check[]
  exposures: { sector: Exposure[]; country: Exposure[] }
  characteristics: { metric: string; label: string; portfolio: number; benchmark: number; better: string; pass: boolean }[]
  skipped: { company_id: string; ticker: string; name: string; reason: string }[]
  cash: number
}

export type BacktestResponse = {
  key: string
  stats: Record<string, number | null>
  series: { date: string; portfolio: number; benchmark: number; relative: number; excess: number }[]
  calendar: { year: number; portfolio: number; benchmark: number; excess: number }[]
  quintiles: { region: string; quintile: number; annualised: number; n: number }[]
  quintile_spread: { region: string; mean: number; periods: number; hit_rate: number; annualised: number }[]
  rebalances: { date: string; holdings: number; turnover: number; cost: number; passed: number; universe: number; pass_ret: number; fail_ret: number }[]
  holdings: { date: string; weights: Record<string, number> }[]
}
