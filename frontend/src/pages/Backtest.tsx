import { useEffect, useMemo, useState } from 'react'
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api'
import { C, axis, grid, tooltipStyle } from '../components/charts'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Card, ErrorBox, Loading, Slider, Stat } from '../components/ui'
import { num, pct, signedPct } from '../format'
import { useApp, useAsync } from '../state'
import type { BacktestParams } from '../types'

const SHORT_REGION: Record<string, string> = { 'North America': 'N. America', 'Pacific ex Japan': 'Pacific ex JP' }

export function Backtest() {
  const { meta, screen, portfolio, backtest, setBacktest } = useApp()
  const [refresh, setRefresh] = useState(0)
  const { data, error, loading } = useAsync(
    () => api.backtest(screen, portfolio, backtest, refresh > 0), [screen, portfolio, backtest, refresh])
  const [draft, setDraft] = useState<BacktestParams>(backtest)
  useEffect(() => setDraft(backtest), [backtest])
  const dirty = JSON.stringify(draft) !== JSON.stringify(backtest)
  const s = data?.stats ?? {}
  const regions = useMemo(() => [...new Set((data?.quintiles ?? []).map((q) => q.region))], [data])
  const quintData = useMemo(() => regions.map((r) => {
    const row: Record<string, any> = { region: r }
    for (const q of data!.quintiles.filter((x) => x.region === r)) row[`Q${q.quintile}`] = q.annualised
    return row
  }), [data, regions])
  const passFail = useMemo(() => {
    const rb = data?.rebalances ?? []
    const per = 12 / backtest.rebalance_months
    const ann = (k: 'pass_ret' | 'fail_ret') => Math.pow(rb.reduce((p, r) => p * (1 + (r[k] ?? 0)), 1), per / Math.max(rb.length, 1)) - 1
    return { pass: ann('pass_ret'), fail: ann('fail_ret') }
  }, [data, backtest.rebalance_months])
  const dates = meta.as_of_dates

  const rebalCols: Column[] = [
    { key: 'date', label: 'Rebalance' },
    { key: 'universe', label: 'Universe', align: 'right' },
    { key: 'passed', label: 'Passed filters', align: 'right' },
    { key: 'holdings', label: 'Holdings', align: 'right' },
    { key: 'turnover', label: 'Turnover (one-way)', align: 'right', render: (r) => pct(r.turnover) },
    { key: 'cost', label: 'Cost', align: 'right', render: (r) => pct(r.cost, 2) },
    { key: 'pass_ret', label: 'Passers next qtr', align: 'right', render: (r) => signedPct(r.pass_ret) },
    { key: 'fail_ret', label: 'Failers next qtr', align: 'right', render: (r) => signedPct(r.fail_ret) },
  ]

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1><span className="step-chip">4</span>Backtest</h1>
          <p className="lede">Everything is point in time: statements are used only after their filing date, delisted companies
            keep their final return, and the screen and portfolio are rebuilt each quarter with the parameters set on the
            screener and portfolio pages.</p>
        </div>
      </header>
      <div className="layout-side">
        <aside className="side-panel">
          <Card title="Backtest settings">
            <label className="field"><span className="field-label">Start</span>
              <select value={draft.start} onChange={(e) => setDraft({ ...draft, start: e.target.value })}>
                {dates.filter((d) => d >= '2013-01-01').map((d) => <option key={d}>{d}</option>)}
              </select></label>
            <label className="field"><span className="field-label">End</span>
              <select value={draft.end ?? ''} onChange={(e) => setDraft({ ...draft, end: e.target.value || null })}>
                <option value="">Latest</option>
                {dates.filter((d) => d > draft.start).map((d) => <option key={d}>{d}</option>)}
              </select></label>
            <Slider label="Rebalance every" value={draft.rebalance_months} min={1} max={12} step={1}
              format={(v) => `${v} month${v > 1 ? 's' : ''}`} onChange={(v) => setDraft({ ...draft, rebalance_months: v })} />
            <Slider label="Trading cost (one-way)" value={draft.cost_bps} min={0} max={150} step={5}
              format={(v) => `${v} bp`} onChange={(v) => setDraft({ ...draft, cost_bps: v })} />
          </Card>
          <div className="side-actions">
            <button className="btn primary" disabled={!dirty} onClick={() => setBacktest(draft)}>Run</button>
            <button className="btn ghost" onClick={() => setRefresh((r) => r + 1)} disabled={loading}>Re-run</button>
          </div>
          <p className="muted small">Uses the screen and portfolio settings currently applied. Results are cached by parameters.</p>
        </aside>
        <div className="content">
          {!meta.demo && (
            <div className="error-box">Survivorship bias: only today's constituents are in the database, so this backtest
              ignores companies that left the index or were delisted. Treat the results as optimistic until a history of
              holdings files has been archived.</div>
          )}
          {error && <ErrorBox error={error} />}
          {loading && <Loading label={data ? 'Re-running…' : 'Running backtest — about 30 seconds the first time, cached after'} />}
          {data && (
            <>
              <div className="stats">
                <Stat label="Return a year" value={pct(s.cagr)} sub={`benchmark ${pct(s.bench_cagr)}`} />
                <Stat label="Excess a year" value={signedPct(s.excess)} tone={(s.excess ?? 0) > 0 ? 'good' : 'bad'} sub="target +3.0%" />
                <Stat label="Tracking error" value={pct(s.tracking_error)} sub="expected 5–8%" />
                <Stat label="Information ratio" value={num(s.information_ratio, 2)} sub={`hit rate ${pct(s.hit_rate, 0)}`} />
                <Stat label="Turnover a year" value={pct(s.turnover_annual, 0)} sub="target 25–40%"
                  tone={(s.turnover_annual ?? 0) > 0.4 ? 'bad' : 'good'} />
                <Stat label="Max relative drawdown" value={pct(s.max_relative_drawdown)} sub={`absolute ${pct(s.max_drawdown)}`} />
              </div>
              <Card title="Growth of 1 (log scale) and relative performance">
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={data.series}>
                    <CartesianGrid {...grid} />
                    <XAxis dataKey="date" tick={axis} tickFormatter={(d) => String(d).slice(0, 4)} minTickGap={40} />
                    <YAxis yAxisId="l" tick={axis} scale="log" domain={['auto', 'auto']} tickFormatter={(v) => v.toFixed(1)} width={40} />
                    <YAxis yAxisId="r" orientation="right" tick={axis} domain={['auto', 'auto']} tickFormatter={(v) => v.toFixed(2)} width={40} />
                    <Tooltip {...tooltipStyle} formatter={(v: any) => Number(v).toFixed(3)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Area isAnimationActive={false} yAxisId="r" dataKey="relative" name="Relative (right)" fill={C.secondary} fillOpacity={0.12} stroke={C.secondary} strokeWidth={1} />
                    <Line isAnimationActive={false} yAxisId="l" dataKey="portfolio" name="Portfolio" stroke={C.primary} strokeWidth={2} dot={false} />
                    <Line isAnimationActive={false} yAxisId="l" dataKey="benchmark" name="Benchmark" stroke={C.neutral} strokeWidth={1.5} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </Card>
              <div className="grid-2">
                <Card title="Screen test: annualised return by score quintile">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={quintData}>
                      <CartesianGrid {...grid} vertical={false} />
                      <XAxis dataKey="region" tick={axis} interval={0} tickFormatter={(r) => SHORT_REGION[r] ?? r} />
                      <YAxis tick={axis} tickFormatter={(v) => pct(v, 0)} width={44} />
                      <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {[1, 2, 3, 4, 5].map((q) => <Bar isAnimationActive={false} key={q} dataKey={`Q${q}`} name={q === 1 ? 'Q1 (top)' : q === 5 ? 'Q5 (bottom)' : `Q${q}`} fill={C.quint[q - 1]} />)}
                    </BarChart>
                  </ResponsiveContainer>
                  <table className="mini wide">
                    <thead><tr><th>Region</th><th className="num">Q1 − Q5 a year</th><th className="num">Quarters Q1 beat Q5</th></tr></thead>
                    <tbody>{data.quintile_spread.map((r) => (
                      <tr key={r.region}><td>{r.region}</td><td className="num">{signedPct(r.annualised)}</td>
                        <td className="num">{pct(r.hit_rate, 0)} of {r.periods}</td></tr>))}
                      <tr className="pillar-row"><td>Hard filters: passers vs failers</td>
                        <td className="num">{signedPct(passFail.pass - passFail.fail)}</td>
                        <td className="num">{pct(passFail.pass)} vs {pct(passFail.fail)}</td></tr>
                    </tbody>
                  </table>
                  <p className="muted small">Quintiles rank every non-financial with enough history on the composite score, ignoring the other hard filters, so the score is tested across its whole range. Equal-weighted, within region.</p>
                </Card>
                <Card title="Calendar-year excess return">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={data.calendar}>
                      <CartesianGrid {...grid} vertical={false} />
                      <XAxis dataKey="year" tick={axis} />
                      <YAxis tick={axis} tickFormatter={(v) => pct(v, 0)} width={44} />
                      <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
                      <ReferenceLine y={0} stroke={C.neutral} />
                      <Bar isAnimationActive={false} dataKey="excess" name="Excess vs benchmark">
                        {data.calendar.map((c) => <Cell key={c.year} fill={c.excess >= 0 ? C.good : C.bad} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <ResponsiveContainer width="100%" height={140}>
                    <LineChart data={data.rebalances}>
                      <CartesianGrid {...grid} />
                      <XAxis dataKey="date" tick={axis} tickFormatter={(d) => String(d).slice(0, 4)} minTickGap={40} />
                      <YAxis tick={axis} tickFormatter={(v) => pct(v, 0)} width={44} />
                      <Tooltip {...tooltipStyle} formatter={(v: any) => pct(v)} />
                      <Line isAnimationActive={false} dataKey="turnover" name="Turnover per rebalance" stroke={C.secondary} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>
              </div>
              <Card title={`Rebalances (${data.rebalances.length})`}>
                <DataTable rows={data.rebalances} columns={rebalCols} rowKey={(r) => r.date} initialSort={{ key: 'date', dir: 'desc' }} pageSize={20} />
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
