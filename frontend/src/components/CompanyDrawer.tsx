import { useEffect } from 'react'
import type { ReactElement } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api'
import { fmtMetric, pct, usd } from '../format'
import { useApp, useAsync } from '../state'
import { C, axis, grid, tooltipStyle } from './charts'
import { Badge, ErrorBox, Loading, PassMark, ScoreBar } from './ui'

export function CompanyDrawer() {
  const { company, openCompany, asOf, meta } = useApp()
  const navigate = useNavigate()
  const { data, error, loading } = useAsync(
    () => (company ? api.company(company, asOf) : Promise.resolve(null)), [company, asOf])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') openCompany(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openCompany])

  if (!company) return null
  const c = data?.company
  const s = data?.screen
  const hist = (data?.history ?? []).slice(-8)
  const first = hist[0]
  const indexed = hist.map((h) => ({
    year: h.fiscal_year,
    revenue: first?.revenue ? (h.revenue / first.revenue) * 100 : null,
    receivables: first?.receivables ? (h.receivables / first.receivables) * 100 : null,
    shares: first?.shares_diluted ? (h.shares_diluted / first.shares_diluted) * 100 : null,
  }))
  const prices = (data?.prices ?? []).filter((_, i, a) => i % 3 === 0 || i === a.length - 1)

  return (
    <div className="drawer-backdrop" onClick={() => openCompany(null)}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Company detail">
        <button className="drawer-close" onClick={() => openCompany(null)} aria-label="Close">×</button>
        {loading && !data && <Loading />}
        {error && <ErrorBox error={error} />}
        {c && (
          <>
            <header className="drawer-head">
              <div className="muted small">{c.ticker} · {c.country} · {c.sector}</div>
              <h2>{c.name}</h2>
              <div className="drawer-tags">
                {s?.passed ? <Badge tone="good">Passes all hard filters</Badge> : <Badge tone="bad">Excluded</Badge>}
                {s?.rank != null && <Badge tone="accent">Rank #{s.rank}</Badge>}
                {s?.in_benchmark ? <Badge>Benchmark</Badge> : <Badge tone="warn">Off-benchmark</Badge>}
                {c.delisted_date && <Badge tone="bad">Delisted {c.delisted_date} ({c.delist_reason})</Badge>}
                <span className="muted small">Mkt cap {usd(s?.mcap_usd)} · ADV {usd(s?.adv_usd)}</span>
                <button className="btn" onClick={() => { const id = company; openCompany(null); navigate(`/stock/${encodeURIComponent(id)}`) }}>
                  Open full profile
                </button>
              </div>
            </header>

            {s && (
              <div className="drawer-grid">
                <section>
                  <h4>Hard filters</h4>
                  <ul className="checklist">
                    {meta.filters.map((f) => {
                      const failed = (s.failed ?? []).includes(f.key)
                      return (
                        <li key={f.key} className={failed ? 'fail' : ''}>
                          <PassMark pass={!failed} /> {f.label}
                          {!f.applies_to_financials && c.sector === 'Financials' && <span className="muted"> (n/a)</span>}
                        </li>
                      )
                    })}
                  </ul>
                </section>
                <section>
                  <h4>Scores {s.composite != null && <span className="muted">· composite {s.composite.toFixed(0)}</span>}</h4>
                  {s.composite == null && <p className="muted small">Scores are calculated only for names that pass the hard filters.</p>}
                  <table className="mini">
                    <tbody>
                      {meta.pillars.map((p) => (
                        <tr key={p} className="pillar-row">
                          <td>{p}</td><td /><td><ScoreBar value={s[`p_${p}`]} /></td>
                        </tr>
                      )).flatMap((row, i) => [row, ...meta.metrics.filter((m) => m.pillar === meta.pillars[i]).map((m) => (
                        <tr key={m.key}>
                          <td className="indent">{m.label}</td>
                          <td className="num">{fmtMetric(m.key, s[m.key])}</td>
                          <td><ScoreBar value={s[`s_${m.key}`]} width={48} /></td>
                        </tr>
                      ))])}
                    </tbody>
                  </table>
                  <p className="muted small">ROE spread = 5y median ROE {pct(s.roe_median)} − cost of equity {pct(s.cost_of_equity)}.</p>
                </section>
              </div>
            )}

            <div className="chart-grid">
              <ChartBox title="ROE vs cost of equity">
                <LineChart data={hist}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="fiscal_year" tick={axis} />
                  <YAxis tick={axis} tickFormatter={(v) => pct(v, 0)} width={44} />
                  <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
                  {s?.cost_of_equity != null && (
                    <ReferenceLine y={s.cost_of_equity} stroke={C.bad} strokeDasharray="4 3" label={{ value: 'CoE', fill: C.bad, fontSize: 10, position: 'right' }} />
                  )}
                  <Line isAnimationActive={false} dataKey="roe" name="ROE" stroke={C.primary} strokeWidth={2} dot={{ r: 2 }} />
                  <Line isAnimationActive={false} dataKey="roic" name="ROIC" stroke={C.secondary} strokeWidth={1.5} dot={false} />
                </LineChart>
              </ChartBox>
              <ChartBox title="Net income vs free cash flow">
                <BarChart data={hist}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="fiscal_year" tick={axis} />
                  <YAxis tick={axis} tickFormatter={(v) => usd(v)} width={54} />
                  <Tooltip {...tooltipStyle} formatter={(v: any) => usd(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar isAnimationActive={false} dataKey="net_income" name="Net income" fill={C.neutral} />
                  <Bar isAnimationActive={false} dataKey="fcf" name="FCF" fill={C.primary} />
                </BarChart>
              </ChartBox>
              <ChartBox title="Receivables vs revenue (indexed)">
                <LineChart data={indexed}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="year" tick={axis} />
                  <YAxis tick={axis} width={40} />
                  <Tooltip {...tooltipStyle} formatter={(v: any) => Number(v).toFixed(0)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line isAnimationActive={false} dataKey="revenue" name="Revenue" stroke={C.primary} strokeWidth={2} dot={false} />
                  <Line isAnimationActive={false} dataKey="receivables" name="Receivables" stroke={C.secondary} strokeWidth={2} dot={false} />
                </LineChart>
              </ChartBox>
              <ChartBox title="Diluted share count (indexed)">
                <LineChart data={indexed}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="year" tick={axis} />
                  <YAxis tick={axis} width={40} domain={['auto', 'auto']} />
                  <Tooltip {...tooltipStyle} formatter={(v: any) => Number(v).toFixed(1)} />
                  <Line isAnimationActive={false} dataKey="shares" name="Shares" stroke={C.primary} strokeWidth={2} dot={{ r: 2 }} />
                </LineChart>
              </ChartBox>
              <ChartBox title="Total return vs benchmark" wide>
                <LineChart data={prices}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="date" tick={axis} tickFormatter={(d) => String(d).slice(0, 4)} minTickGap={30} />
                  <YAxis tick={axis} width={40} scale="log" domain={['auto', 'auto']} tickFormatter={(v) => v.toFixed(1)} />
                  <Tooltip {...tooltipStyle} formatter={(v: any) => Number(v).toFixed(2)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line isAnimationActive={false} dataKey="index" name={c.ticker} stroke={C.primary} strokeWidth={2} dot={false} />
                  <Line isAnimationActive={false} dataKey="bench_index" name="Benchmark" stroke={C.neutral} strokeWidth={1.5} dot={false} />
                </LineChart>
              </ChartBox>
            </div>

          </>
        )}
      </aside>
    </div>
  )
}

function ChartBox({ title, children, wide }: { title: string; children: ReactElement; wide?: boolean }) {
  return (
    <div className={`chart-box ${wide ? 'wide' : ''}`}>
      <div className="chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={170}>{children}</ResponsiveContainer>
    </div>
  )
}
