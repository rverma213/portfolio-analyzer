import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { C, axis, grid, tooltipStyle } from '../components/charts'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Badge, Card, ErrorBox, Loading, PassMark, ScoreBar, Slider, Stat, Tabs, Toggle } from '../components/ui'
import { fmtMetric, num, pct, signedPct, usd } from '../format'
import { useApp, useAsync } from '../state'
import type { PortfolioParams, Row } from '../types'

// Raw values (weights as fractions), so the file can be re-used in a spreadsheet without parsing.
const CSV_COLUMNS = [
  'ticker', 'name', 'country', 'sector', 'weight', 'target_weight', 'conviction', 'rank',
  'composite', 'roe_median', 'fcf_conversion', 'fcf_yield', 'earnings_yield', 'leverage', 'days_to_trade',
  'in_benchmark', 'company_id',
]

function downloadCsv(rows: Row[], filename: string) {
  const cell = (v: unknown) => {
    const s = v == null ? '' : String(v)
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const sorted = [...rows].sort((a, b) => b.weight - a.weight)
  const lines = [CSV_COLUMNS.join(','), ...sorted.map((r) => CSV_COLUMNS.map((c) => cell(r[c])).join(','))]
  // Leading BOM so Excel reads names with accents correctly.
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function Portfolio() {
  const { meta, asOf, screen, portfolio, setPortfolio, openCompany } = useApp()
  const { data, error, loading } = useAsync(
    () => api.portfolio(asOf, screen, portfolio), [asOf, screen, portfolio])
  const [draft, setDraft] = useState<PortfolioParams>(portfolio)
  const [exp, setExp] = useState<'sector' | 'country'>('sector')
  useEffect(() => setDraft(portfolio), [portfolio])
  const dirty = JSON.stringify(draft) !== JSON.stringify(portfolio)
  const set = <K extends keyof PortfolioParams>(k: K, v: PortfolioParams[K]) => setDraft({ ...draft, [k]: v })

  const columns: Column[] = [
    { key: 'ticker', label: 'Ticker', width: 86 },
    { key: 'name', label: 'Name' },
    { key: 'country', label: 'Country' },
    { key: 'sector', label: 'Sector' },
    { key: 'weight', label: 'Weight', align: 'right', render: (r) => <strong>{pct(r.weight, 2)}</strong> },
    { key: 'conviction', label: 'Conviction' },
    { key: 'rank', label: 'Rank', align: 'right' },
    { key: 'composite', label: 'Score', render: (r) => <ScoreBar value={r.composite} width={44} /> },
    { key: 'roe_median', label: 'ROE 5y', align: 'right', render: (r) => pct(r.roe_median) },
    { key: 'fcf_yield', label: 'FCF yield', align: 'right', render: (r) => pct(r.fcf_yield) },
    { key: 'leverage', label: 'ND/EBITDA', align: 'right', render: (r) => fmtMetric('leverage', r.leverage) },
    { key: 'days_to_trade', label: 'Days to trade', align: 'right', render: (r) => num(r.days_to_trade, 1),
      title: `Position ÷ (${pct(portfolio.adv_participation, 0)} of ADV) at ${usd(portfolio.aum_usd)} AUM` },
    { key: 'in_benchmark', label: '', render: (r) => (r.in_benchmark ? null : <Badge tone="warn">Off-bench</Badge>), sortValue: (r) => (r.in_benchmark ? 0 : 1) },
  ]

  const holdings = data?.holdings ?? []
  const top10 = [...holdings].sort((a, b) => b.weight - a.weight).slice(0, 10).reduce((s, r) => s + r.weight, 0)
  const hardChecks = data?.checks.filter((c) => !c.advisory) ?? []

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1><span className="step-chip">3</span>Portfolio</h1>
          <p className="lede">Names are added in rank order (holdings still in the top 40% are kept first) and sized by conviction:
            2.5%, 1.75% or 1.0%. Each position is capped by the 4% maximum, by liquidity (5 days at 25% of ADV), and by sector and
            country bands around the benchmark. Weights are then scaled so cash stays under 3%.</p>
        </div>
      </header>
      <div className="layout-side">
        <aside className="side-panel">
          <Card title="Construction">
            <Slider label="AUM" value={draft.aum_usd} min={2.5e7} max={2e9} step={2.5e7} format={usd}
              onChange={(v) => set('aum_usd', v)} hint="Drives the liquidity cap" />
            <Slider label="Target holdings" value={draft.target_holdings} min={40} max={80} step={5}
              onChange={(v) => set('target_holdings', v)} />
            <Slider label="Max position" value={draft.max_position} min={0.02} max={0.06} step={0.0025}
              format={(v) => pct(v, 2)} onChange={(v) => set('max_position', v)} />
            <Slider label="Sector band" value={draft.sector_band} min={0.02} max={0.2} step={0.01}
              format={(v) => `±${pct(v, 0)}`} onChange={(v) => set('sector_band', v)} />
            <Slider label="Country band" value={draft.country_band} min={0.02} max={0.2} step={0.01}
              format={(v) => `±${pct(v, 0)}`} onChange={(v) => set('country_band', v)} hint={`US and Japan ±${pct(draft.country_band_large, 0)}`} />
            <Slider label="Days of ADV" value={draft.adv_days} min={1} max={10} step={0.5}
              onChange={(v) => set('adv_days', v)} />
            <Slider label="Off-benchmark limit" value={draft.off_benchmark_max} min={0} max={0.2} step={0.01}
              format={(v) => pct(v, 0)} onChange={(v) => set('off_benchmark_max', v)} />
            <Toggle label="Include financials list" checked={draft.include_financials}
              onChange={(v) => set('include_financials', v)} />
          </Card>
          <div className="side-actions">
            <button className="btn primary" disabled={!dirty} onClick={() => setPortfolio(draft)}>Apply</button>
            <button className="btn ghost" onClick={() => setDraft(meta.defaults.portfolio)}>Reset to defaults</button>
          </div>
        </aside>
        <div className="content">
          {error && <ErrorBox error={error} />}
          {loading && !data && <Loading />}
          {data && (
            <>
              <div className="stats">
                <Stat label="Holdings" value={holdings.length} sub={`as of ${data.as_of}`} />
                <Stat label="Cash" value={pct(data.cash, 2)} />
                <Stat label="Top 10 weight" value={pct(top10)} />
                <Stat label="Limits met" value={`${hardChecks.filter((c) => c.pass).length}/${hardChecks.length}`}
                  tone={hardChecks.every((c) => c.pass) ? 'good' : 'bad'} />
              </div>
              <div className="grid-2">
                <Card title="Limit checks">
                  <table className="mini wide">
                    <thead><tr><th /><th>Rule</th><th>Limit</th><th>Actual</th></tr></thead>
                    <tbody>{data.checks.map((c) => (
                      <tr key={c.rule} className={c.advisory ? 'muted' : ''}>
                        <td>{c.advisory ? <span className="mark warn">i</span> : <PassMark pass={c.pass} />}</td>
                        <td>{c.rule}</td><td>{c.limit}</td><td>{String(c.actual)}</td>
                      </tr>))}
                    </tbody>
                  </table>
                  <p className="muted small">Benchmark floors are reported rather than forced: a concentrated long-only book cannot always hold every sector near its benchmark weight.</p>
                </Card>
                <Card title="Quality vs benchmark (weighted medians)">
                  <table className="mini wide">
                    <thead><tr><th /><th>Metric</th><th className="num">Portfolio</th><th className="num">Benchmark</th></tr></thead>
                    <tbody>{data.characteristics.map((c) => (
                      <tr key={c.metric}>
                        <td><PassMark pass={c.pass} /></td><td>{c.label} <span className="muted small">({c.better} is better)</span></td>
                        <td className="num">{fmtMetric(c.metric, c.portfolio)}</td><td className="num">{fmtMetric(c.metric, c.benchmark)}</td>
                      </tr>))}
                    </tbody>
                  </table>
                </Card>
              </div>
              <Card title="Active exposure" actions={<Tabs value={exp} onChange={setExp} tabs={[{ key: 'sector', label: 'Sector' }, { key: 'country', label: 'Country' }]} />}>
                <ResponsiveContainer width="100%" height={exp === 'sector' ? 300 : 360}>
                  <BarChart data={data.exposures[exp].filter((e) => e.portfolio > 0.001 || e.benchmark > 0.004)} layout="vertical" margin={{ left: 30 }}>
                    <CartesianGrid {...grid} horizontal={false} />
                    <XAxis type="number" tick={axis} tickFormatter={(v) => pct(v, 0)} />
                    <YAxis type="category" dataKey="name" tick={axis} width={150} interval={0} />
                    <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar isAnimationActive={false} dataKey="benchmark" name="Benchmark" fill={C.neutral} barSize={8} />
                    <Bar isAnimationActive={false} dataKey="portfolio" name="Portfolio" fill={C.primary} barSize={8} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="exposure-table">
                  {data.exposures[exp].filter((e) => e.portfolio > 0 || e.benchmark > 0.004).map((e) => (
                    <span key={e.name} className={`chip ${!e.within ? 'bad' : e.below_floor ? 'warn' : ''}`}>
                      {e.name}: {signedPct(e.active)}
                    </span>
                  ))}
                </div>
              </Card>
              <Card title={`Holdings (${holdings.length})`} actions={
                <button className="btn ghost" disabled={!holdings.length}
                  onClick={() => downloadCsv(holdings, `portfolio-analyzer-${data.as_of}.csv`)}>Download CSV</button>}>
                <DataTable rows={holdings} columns={columns} onRowClick={(r) => openCompany(r.company_id)}
                  initialSort={{ key: 'weight', dir: 'desc' }} pageSize={80} />
              </Card>
              {data.skipped.length > 0 && (
                <Card title={`Skipped by limits (${data.skipped.length})`}>
                  <p className="muted small">Higher-ranked names that could not be held, in rank order.</p>
                  <div className="chips wrap">
                    {data.skipped.map((s) => (
                      <button key={s.company_id} className="chip clickable" onClick={() => openCompany(s.company_id)}>
                        {s.ticker} · {s.reason}
                      </button>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
