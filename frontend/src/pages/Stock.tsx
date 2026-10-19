import { useEffect, useMemo, useState } from 'react'
import type { ReactElement } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import { api } from '../api'
import { C, axis, grid, tooltipStyle } from '../components/charts'
import { StockPicker } from '../components/StockPicker'
import { Badge, Card, ErrorBox, Loading, PassMark, ScoreBar, Stat, Tabs } from '../components/ui'
import { fmtMetric, num, pct, signedPct, times, usd } from '../format'
import { useApp, useAsync } from '../state'
import type { Row, StockResponse } from '../types'

const LAST_KEY = 'pa.stock'
const RANGES = [
  { key: '1y', label: '1Y', months: 12 }, { key: '3y', label: '3Y', months: 36 }, { key: '5y', label: '5Y', months: 60 },
  { key: '10y', label: '10Y', months: 120 }, { key: 'all', label: 'All', months: Infinity },
] as const
type RangeKey = typeof RANGES[number]['key']

function remembered(): string | null {
  try { return localStorage.getItem(LAST_KEY) } catch { return null }
}

export function Stock() {
  const { asOf } = useApp()
  const { id } = useParams()
  const navigate = useNavigate()
  const list = useAsync(() => api.stocks(), [])

  // No stock in the URL: reopen the last one viewed, else the largest benchmark weight.
  useEffect(() => {
    if (id || !list.data?.length) return
    const last = remembered()
    const fallback = [...list.data].sort((a, b) => (b.bench_weight_file ?? 0) - (a.bench_weight_file ?? 0))[0]
    const start = list.data.some((o) => o.company_id === last) ? last! : fallback.company_id
    navigate(`/stock/${encodeURIComponent(start)}`, { replace: true })
  }, [id, list.data, navigate])

  useEffect(() => {
    if (id) try { localStorage.setItem(LAST_KEY, id) } catch { /* storage unavailable */ }
  }, [id])

  const { data, error, loading } = useAsync(
    () => (id ? api.stock(id, asOf) : Promise.resolve(null)), [id, asOf])

  return (
    <div className="page">
      <header className="page-head stock-head">
        <div>
          <h1>Single stock</h1>
          <p className="lede">Everything stored for one company: prices, returns and risk against the benchmark, trading volume
            and every annual statement filed by the as-of date.</p>
        </div>
        {list.data && (
          <StockPicker options={list.data} value={id ?? null}
            onChange={(cid) => navigate(`/stock/${encodeURIComponent(cid)}`)} />
        )}
      </header>
      {list.error && <ErrorBox error={list.error} />}
      {error && <ErrorBox error={error} />}
      {loading && !data && <Loading />}
      {data && <Profile data={data} reloading={loading} />}
    </div>
  )
}

function Profile({ data, reloading }: { data: StockResponse; reloading: boolean }) {
  const [range, setRange] = useState<RangeKey>('all')
  const [view, setView] = useState<'index' | 'relative' | 'drawdown'>('index')
  const [win, setWin] = useState<'12' | '36'>('36')
  const c = data.company
  const m = data.market
  const s = data.screen

  const series = useMemo((): Row[] => {
    const months = RANGES.find((r) => r.key === range)!.months
    const rows = data.series.slice(Number.isFinite(months) ? -(months + 1) : 0)
    const base = rows[0]
    if (!base) return []
    // Rebase both indices to 100 at the start of the chosen range.
    return rows.map((r) => ({
      ...r,
      index: (r.index / base.index) * 100,
      bench_index: (r.bench_index / base.bench_index) * 100,
      relative: ((r.index / base.index) / (r.bench_index / base.bench_index)) * 100,
    }))
  }, [data.series, range])

  const xTicks = { dataKey: 'date', tick: axis, minTickGap: 40, tickFormatter: (d: string) => (range === '1y' ? d.slice(0, 7) : d.slice(0, 4)) }
  const last = series[series.length - 1]
  const stockName = c.ticker as string

  return (
    <div className={`stock-profile ${reloading ? 'reloading' : ''}`}>
      <Card className="stock-id">
        <div className="stock-title">
          <div>
            <div className="muted small">{c.ticker}{c.local_ticker && c.local_ticker !== c.ticker ? ` · local ${c.local_ticker}` : ''}{c.exchange ? ` · ${c.exchange}` : ''}</div>
            <h2>{c.name}</h2>
          </div>
          <div className="drawer-tags">
            <Badge>{c.country}</Badge>
            <Badge>{c.region}</Badge>
            <Badge>{c.sector}</Badge>
            {m.in_benchmark ? <Badge tone="accent">Benchmark member</Badge> : <Badge tone="warn">Off-benchmark</Badge>}
            {s && (s.passed ? <Badge tone="good">Passes hard filters</Badge> : <Badge tone="bad">Excluded by screen</Badge>)}
            {s?.rank != null && <Badge tone="accent">Rank #{s.rank}</Badge>}
          </div>
        </div>
      </Card>

      <div className="stats">
        <Stat label="Price (USD)" value={`$${num(m.price, m.price < 10 ? 2 : 1)}`} sub={`12m range $${num(m.low_12m, 2)} – $${num(m.high_12m, 2)}`} />
        <Stat label="Market cap" value={usd(m.mcap_usd)} sub={s?.ev_usd != null ? `EV ${usd(s.ev_usd)}` : `at ${m.date}`} />
        <Stat label="Avg daily value traded" value={usd(m.adv_usd)} sub={`12m average ${usd(m.adv_12m)}`} />
        <Stat label="Benchmark weight" value={pct(c.bench_weight_file, 3)} sub="in the iShares holdings file" />
        <Stat label="1-year return" value={signedPct(data.returns.find((r) => r.key === '1y')?.stock)}
          tone={(data.returns.find((r) => r.key === '1y')?.stock ?? 0) >= 0 ? 'good' : 'bad'}
          sub={`benchmark ${signedPct(data.returns.find((r) => r.key === '1y')?.benchmark)}`} />
        <Stat label="Price history" value={`${Math.floor((m.months - 1) / 12)}y ${(m.months - 1) % 12}m`} sub={`since ${m.first_month.slice(0, 7)}`} />
      </div>

      <Card title="Returns" actions={<span className="muted small">Total return in USD, dividends included · to {data.as_of} · 3Y and longer are annualised</span>}>
        <div className="table-wrap">
          <table className="table returns-table">
            <thead><tr><th />{data.returns.map((r) => <th key={r.key} className="num">{r.label}</th>)}</tr></thead>
            <tbody>
              <tr><td><strong>{stockName}</strong></td>{data.returns.map((r) => <td key={r.key} className="num">{signedPct(r.stock)}</td>)}</tr>
              <tr><td className="muted">Benchmark</td>{data.returns.map((r) => <td key={r.key} className="num muted">{signedPct(r.benchmark)}</td>)}</tr>
              <tr><td>Excess</td>{data.returns.map((r) => (
                <td key={r.key} className={`num ${r.excess == null ? '' : r.excess >= 0 ? 'pos' : 'neg'}`}>{signedPct(r.excess)}</td>))}</tr>
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Total return vs benchmark" actions={
        <>
          <Tabs value={view} onChange={setView} tabs={[
            { key: 'index', label: 'Growth of 100' }, { key: 'relative', label: 'Relative' }, { key: 'drawdown', label: 'Drawdown' }]} />
          <Tabs value={range} onChange={setRange} tabs={RANGES.map((r) => ({ key: r.key, label: r.label }))} />
        </>}>
        <ResponsiveContainer width="100%" height={300}>
          {view === 'index' ? (
            <LineChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis tick={axis} width={48} scale="log" domain={['auto', 'auto']} allowDataOverflow tickFormatter={(v) => num(v, 0)} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => num(v, 1)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={100} stroke={C.neutral} strokeDasharray="3 3" />
              <Line isAnimationActive={false} dataKey="index" name={stockName} stroke={C.primary} strokeWidth={2} dot={false} />
              <Line isAnimationActive={false} dataKey="bench_index" name="Benchmark" stroke={C.secondary} strokeWidth={1.5} dot={false} />
            </LineChart>
          ) : view === 'relative' ? (
            <LineChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis tick={axis} width={48} scale="log" domain={['auto', 'auto']} allowDataOverflow tickFormatter={(v) => num(v, 0)} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => num(v, 1)} />
              <ReferenceLine y={100} stroke={C.neutral} strokeDasharray="3 3" />
              <Line isAnimationActive={false} dataKey="relative" name={`${stockName} ÷ benchmark`} stroke={C.primary} strokeWidth={2} dot={false} />
            </LineChart>
          ) : (
            <AreaChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis tick={axis} width={48} tickFormatter={(v) => pct(v, 0)} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area isAnimationActive={false} dataKey="drawdown" name={stockName} stroke={C.bad} fill={C.bad} fillOpacity={0.15} />
              <Area isAnimationActive={false} dataKey="bench_drawdown" name="Benchmark" stroke={C.neutral} fill="none" />
            </AreaChart>
          )}
        </ResponsiveContainer>
        <p className="muted small chart-note">
          {view === 'index' && last && <>From 100 at {series[0].date.slice(0, 7)}: {stockName} {num(last.index, 0)}, benchmark {num(last.bench_index, 0)}. Log scale.</>}
          {view === 'relative' && <>Above 100 and rising means {stockName} is beating the benchmark over the chosen period.</>}
          {view === 'drawdown' && <>Fall from the previous peak of the total-return index, from the first month of price history.</>}
          {' '}The benchmark is the cap-weighted return of all benchmark members.
        </p>
      </Card>

      <div className="grid-2">
        <Card title={`Rolling ${win}-month correlation with benchmark`} actions={
          <Tabs value={win} onChange={setWin} tabs={[{ key: '12', label: '12m' }, { key: '36', label: '36m' }]} />}>
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis tick={axis} width={40} domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => num(v, 2)} />
              <ReferenceLine y={0} stroke={C.neutral} />
              <Area isAnimationActive={false} dataKey={`corr_${win}`} name="Correlation" stroke={C.primary} fill={C.primary} fillOpacity={0.15} connectNulls={false} />
            </AreaChart>
          </ResponsiveContainer>
          <p className="muted small chart-note">Correlation of monthly returns over the trailing {win} months. 1 moves with the benchmark, 0 is unrelated. Needs a full window of history.</p>
        </Card>
        <Card title={`Rolling ${win}-month annualised volatility`} actions={
          <Tabs value={win} onChange={setWin} tabs={[{ key: '12', label: '12m' }, { key: '36', label: '36m' }]} />}>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis tick={axis} width={44} tickFormatter={(v) => pct(v, 0)} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line isAnimationActive={false} dataKey={`vol_${win}`} name={stockName} stroke={C.primary} strokeWidth={2} dot={false} />
              <Line isAnimationActive={false} dataKey={`bench_vol_${win}`} name="Benchmark" stroke={C.secondary} strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <p className="muted small chart-note">Standard deviation of monthly returns over the trailing {win} months × √12.</p>
        </Card>
      </div>

      <div className="grid-2">
        <RiskCard data={data} name={stockName} />
        <Card title="Calendar-year returns">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.calendar.map((y) => ({ ...y, label: y.partial ? `${y.year}*` : String(y.year) }))}>
              <CartesianGrid {...grid} />
              <XAxis dataKey="label" tick={axis} minTickGap={4} />
              <YAxis tick={axis} width={48} tickFormatter={(v) => pct(v, 0)} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => signedPct(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={0} stroke={C.neutral} />
              <Bar isAnimationActive={false} dataKey="stock" name={stockName} fill={C.primary} />
              <Bar isAnimationActive={false} dataKey="benchmark" name="Benchmark" fill={C.secondary} />
            </BarChart>
          </ResponsiveContainer>
          <p className="muted small chart-note">* part year: the first year of price history, or the year to date.</p>
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Price and market cap (USD)">
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis yAxisId="p" tick={axis} width={48} domain={['auto', 'auto']} tickFormatter={(v) => `$${num(v, v < 10 ? 2 : 0)}`} />
              <YAxis yAxisId="m" orientation="right" tick={axis} width={58} domain={['auto', 'auto']} tickFormatter={(v) => usd(v)} />
              <Tooltip {...tooltipStyle} formatter={(v: any, n: any) => (n === 'Market cap' ? usd(v) : `$${num(v, 2)}`)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line yAxisId="p" isAnimationActive={false} dataKey="price" name="Price" stroke={C.primary} strokeWidth={2} dot={false} />
              <Line yAxisId="m" isAnimationActive={false} dataKey="mcap_usd" name="Market cap" stroke={C.neutral} strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <p className="muted small chart-note">Month-end close converted to USD. Past market caps use today's share count, so they ignore later share issuance and buybacks.</p>
        </Card>
        <Card title="Trading volume (average daily value traded, USD)">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={series}>
              <CartesianGrid {...grid} />
              <XAxis {...xTicks} />
              <YAxis tick={axis} width={58} tickFormatter={(v) => usd(v)} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => usd(v)} />
              <Bar isAnimationActive={false} dataKey="adv_usd" name="ADV" fill={C.primary} />
            </BarChart>
          </ResponsiveContainer>
          <p className="muted small chart-note">Shares traded in the month × USD price ÷ about 21 trading days.</p>
        </Card>
      </div>

      {s && <ScreenCard s={s} />}
      <Fundamentals rows={data.fundamentals} />
    </div>
  )
}

function RiskCard({ data, name }: { data: StockResponse; name: string }) {
  const cols = data.risk
  const label = (k: string) => (k === 'all' ? 'All history' : k.toUpperCase())
  const rows: [string, (r: Row) => ReactElement | string, string?][] = [
    [`Volatility, ${name}`, (r) => pct(r.vol)],
    ['Volatility, benchmark', (r) => pct(r.bench_vol)],
    ['Correlation', (r) => num(r.correlation, 2)],
    ['Beta', (r) => num(r.beta, 2), 'How much the stock moves per 1% move in the benchmark'],
    ['Tracking error', (r) => pct(r.tracking_error), 'Volatility of the monthly return difference, annualised'],
    [`Max drawdown, ${name}`, (r) => pct(r.max_drawdown)],
    ['Max drawdown, benchmark', (r) => pct(r.bench_max_drawdown)],
    ['Best month', (r) => signedPct(r.best_month)],
    ['Worst month', (r) => signedPct(r.worst_month)],
    ['Months up', (r) => pct(r.positive_months, 0)],
    ['Months beating benchmark', (r) => pct(r.beat_months, 0)],
  ]
  return (
    <Card title="Risk vs benchmark" actions={<span className="muted small">Monthly returns, annualised</span>}>
      <div className="table-wrap">
        <table className="mini wide">
          <thead><tr><th />{cols.map((c) => <th key={c.key} className="num">{label(c.key)}</th>)}</tr></thead>
          <tbody>
            {rows.map(([lbl, fmt, title]) => (
              <tr key={lbl}>
                <td title={title}>{lbl}</td>
                {cols.map((c) => <td key={c.key} className="num">{c.available ? fmt(c) : <span className="muted">–</span>}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small chart-note">A dash means the stock has less price history than the window.</p>
    </Card>
  )
}

function ScreenCard({ s }: { s: Row }) {
  const { meta, asOf } = useApp()
  return (
    <Card title={`Screen and valuation at ${asOf}`} actions={s.composite != null ? <span className="muted small">Composite score {num(s.composite, 0)} · top {pct(1 - s.rank_pct, 0)}</span> : undefined}>
      <div className="screen-grid">
        <section>
          <h4>Hard filters</h4>
          <ul className="checklist">
            {meta.filters.map((f) => {
              const failed = (s.failed ?? []).includes(f.key)
              return <li key={f.key} className={failed ? 'fail' : ''}><PassMark pass={!failed} /> {f.label}</li>
            })}
          </ul>
        </section>
        <section>
          <h4>Valuation</h4>
          <table className="mini wide"><tbody>
            <tr><td>Earnings yield</td><td className="num">{pct(s.earnings_yield)}</td></tr>
            <tr><td>Free cash flow yield (on EV)</td><td className="num">{pct(s.fcf_yield)}</td></tr>
            <tr><td>Book to price</td><td className="num">{num(s.book_to_price, 2)}</td></tr>
            <tr><td>Enterprise value</td><td className="num">{usd(s.ev_usd)}</td></tr>
            <tr><td>Cost of equity ({s.region})</td><td className="num">{pct(s.cost_of_equity)}</td></tr>
          </tbody></table>
        </section>
        <section>
          <h4>Scores {s.composite == null && <span className="muted small">(only for names that pass)</span>}</h4>
          <table className="mini wide"><tbody>
            {meta.metrics.map((mt) => (
              <tr key={mt.key}>
                <td>{mt.label}</td>
                <td className="num">{fmtMetric(mt.key, s[mt.key])}</td>
                <td><ScoreBar value={s[`s_${mt.key}`]} width={44} /></td>
              </tr>
            ))}
          </tbody></table>
        </section>
      </div>
    </Card>
  )
}

type FundLine = { key: string; label: string; fmt: (v: unknown) => string; strong?: boolean }
const FUNDAMENTALS: { group: string; lines: FundLine[] }[] = [
  { group: 'Income statement', lines: [
    { key: 'revenue', label: 'Revenue', fmt: usd, strong: true },
    { key: 'ebitda', label: 'EBITDA', fmt: usd },
    { key: 'ebit', label: 'EBIT (operating income)', fmt: usd },
    { key: 'net_income', label: 'Net income', fmt: usd, strong: true },
    { key: 'tax_rate', label: 'Tax rate', fmt: (v) => pct(v, 0) },
  ] },
  { group: 'Cash flow', lines: [
    { key: 'cfo', label: 'Cash from operations', fmt: usd },
    { key: 'capex', label: 'Capital expenditure', fmt: usd },
    { key: 'fcf', label: 'Free cash flow', fmt: usd, strong: true },
    { key: 'dividends', label: 'Dividends paid', fmt: usd },
  ] },
  { group: 'Balance sheet', lines: [
    { key: 'total_assets', label: 'Total assets', fmt: usd },
    { key: 'equity', label: "Shareholders' equity", fmt: usd },
    { key: 'debt', label: 'Debt', fmt: usd },
    { key: 'cash', label: 'Cash', fmt: usd },
    { key: 'net_debt', label: 'Net debt', fmt: usd },
    { key: 'receivables', label: 'Receivables', fmt: usd },
    { key: 'shares_diluted', label: 'Diluted shares', fmt: (v) => (typeof v === 'number' ? `${(v / 1e6).toFixed(1)}m` : '–') },
  ] },
  { group: 'Ratios', lines: [
    { key: 'roe', label: 'Return on equity', fmt: (v) => pct(v) },
    { key: 'roe_median', label: 'ROE, 5-year median', fmt: (v) => pct(v) },
    { key: 'roic', label: 'Return on invested capital', fmt: (v) => pct(v) },
    { key: 'leverage', label: 'Net debt ÷ EBITDA', fmt: (v) => times(v) },
    { key: 'fcf_conversion', label: 'FCF conversion, 5 years', fmt: (v) => pct(v, 0) },
    { key: 'accruals', label: 'Accruals', fmt: (v) => pct(v) },
    { key: 'sales_growth', label: 'Sales growth, 3-year CAGR', fmt: (v) => signedPct(v) },
    { key: 'dilution', label: 'Share count growth, 3-year CAGR', fmt: (v) => signedPct(v) },
  ] },
]

function Fundamentals({ rows }: { rows: Row[] }) {
  const [all, setAll] = useState(false)
  if (!rows.length) {
    return <Card title="Fundamentals"><p className="muted">No annual statements filed by this date.</p></Card>
  }
  const shown = all ? rows : rows.slice(-10)
  return (
    <Card title={`Fundamentals (${rows.length} fiscal year${rows.length === 1 ? '' : 's'})`} actions={
      <>
        <span className="muted small">USD · source {[...new Set(rows.map((r) => r.source === 'sec' ? 'SEC EDGAR' : 'Yahoo'))].join(', ')}</span>
        {rows.length > 10 && <button className="btn" onClick={() => setAll(!all)}>{all ? 'Last 10 years' : `Show all ${rows.length} years`}</button>}
      </>}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={shown}>
          <CartesianGrid {...grid} />
          <XAxis dataKey="fiscal_year" tick={axis} />
          <YAxis tick={axis} width={58} tickFormatter={(v) => usd(v)} />
          <Tooltip {...tooltipStyle} formatter={(v: any) => usd(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke={C.neutral} />
          <Bar isAnimationActive={false} dataKey="revenue" name="Revenue" fill={C.neutral} />
          <Bar isAnimationActive={false} dataKey="net_income" name="Net income" fill={C.primary} />
          <Bar isAnimationActive={false} dataKey="fcf" name="Free cash flow" fill={C.secondary} />
        </BarChart>
      </ResponsiveContainer>
      <div className="table-wrap">
        <table className="table fund-table">
          <thead>
            <tr><th>Fiscal year</th>{shown.map((r) => <th key={r.fiscal_year} className="num">{r.fiscal_year}</th>)}</tr>
          </thead>
          <tbody>
            {FUNDAMENTALS.map((g) => [
              <tr key={g.group} className="group-row"><td colSpan={shown.length + 1}>{g.group}</td></tr>,
              ...g.lines.map((l) => (
                <tr key={l.key} className={l.strong ? 'strong' : ''}>
                  <td>{l.label}</td>
                  {shown.map((r) => <td key={r.fiscal_year} className={`num ${typeof r[l.key] === 'number' && r[l.key] < 0 ? 'neg' : ''}`}>{l.fmt(r[l.key])}</td>)}
                </tr>
              )),
            ])}
            <tr className="group-row"><td colSpan={shown.length + 1}>Filing</td></tr>
            <tr><td>Period end</td>{shown.map((r) => <td key={r.fiscal_year} className="num muted">{r.period_end}</td>)}</tr>
            <tr><td>Filed</td>{shown.map((r) => <td key={r.fiscal_year} className="num muted">{r.filing_date}{r.filing_estimated ? '*' : ''}</td>)}</tr>
            <tr><td>Source</td>{shown.map((r) => <td key={r.fiscal_year} className="num muted">{r.source === 'sec' ? 'SEC' : 'Yahoo'}</td>)}</tr>
          </tbody>
        </table>
      </div>
      {rows.some((r) => r.filing_estimated) && <p className="muted small chart-note">* estimated filing date: period end + 90 days.</p>}
    </Card>
  )
}
