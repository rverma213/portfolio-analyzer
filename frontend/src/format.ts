const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export const pct = (v: unknown, digits = 1) => (isNum(v) ? `${(v * 100).toFixed(digits)}%` : '–')

export const signedPct = (v: unknown, digits = 1) =>
  isNum(v) ? `${v > 0 ? '+' : ''}${(v * 100).toFixed(digits)}%` : '–'

export const num = (v: unknown, digits = 1) => (isNum(v) ? v.toFixed(digits) : '–')

export const int = (v: unknown) => (isNum(v) ? Math.round(v).toLocaleString() : '–')

export const usd = (v: unknown) => {
  if (!isNum(v)) return '–'
  const a = Math.abs(v)
  if (a >= 1e12) return `$${(v / 1e12).toFixed(1)}tn`
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}bn`
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}m`
  if (a >= 1e3) return `$${(v / 1e3).toFixed(0)}k`
  return `$${v.toFixed(0)}`
}

export const times = (v: unknown, digits = 1) => (isNum(v) ? `${v.toFixed(digits)}x` : '–')

// How each metric is displayed.
export const METRIC_FORMAT: Record<string, (v: unknown) => string> = {
  earnings_yield: (v) => pct(v),
  loss_years: (v) => num(v, 0),
  accruals: (v) => pct(v),
  receivables_gap: (v) => signedPct(v),
  fcf_yield: (v) => pct(v),
  fcf_conversion: (v) => pct(v, 0),
  roe_spread: (v) => signedPct(v),
  roe_stability: (v) => pct(v),
  roic: (v) => pct(v),
  leverage: (v) => times(v),
  dilution: (v) => signedPct(v),
  roe_median: (v) => pct(v),
  book_to_price: (v) => num(v, 2),
}

export const fmtMetric = (key: string, v: unknown) => (METRIC_FORMAT[key] ?? ((x) => num(x, 2)))(v)

export const FILTER_SHORT: Record<string, string> = {
  universe: 'Universe',
  liquidity: 'Liquidity',
  history: 'History',
  fcf_record: 'FCF record',
  profitable: 'Profitable',
  leverage: 'Leverage',
  roe_vs_coe: 'ROE < CoE',
  dilution: 'Dilution',
  receivables: 'Receivables',
}
