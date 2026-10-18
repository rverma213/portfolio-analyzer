import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Badge, Card, ErrorBox, Funnel, Loading, ScoreBar, Slider, Tabs, Toggle } from '../components/ui'
import { FILTER_SHORT, fmtMetric, pct, usd } from '../format'
import { useApp, useAsync } from '../state'
import type { ScreenParams } from '../types'

type Tab = 'ranked' | 'excluded' | 'financials'

export function Screener() {
  const { meta, asOf, screen, setScreen, openCompany } = useApp()
  const { data, error, loading } = useAsync(() => api.screen(asOf, screen), [asOf, screen])
  const [draft, setDraft] = useState<ScreenParams>(screen)
  const [tab, setTab] = useState<Tab>('ranked')
  const [filterKey, setFilterKey] = useState<string | null>(null)
  const [showMetrics, setShowMetrics] = useState(false)
  useEffect(() => setDraft(screen), [screen])

  const dirty = JSON.stringify(draft) !== JSON.stringify(screen)
  const set = <K extends keyof ScreenParams>(k: K, v: ScreenParams[K]) => setDraft({ ...draft, [k]: v })

  const excluded = useMemo(() => {
    const rows = data?.excluded ?? []
    return filterKey ? rows.filter((r) => r.first_failed === filterKey) : rows
  }, [data, filterKey])

  const selectStep = (k: string | null) => {
    setFilterKey(k === 'financials' ? null : k)
    setTab(k === 'financials' ? 'financials' : k ? 'excluded' : 'ranked')
  }

  const base: Column[] = [
    { key: 'ticker', label: 'Ticker', width: 86 },
    { key: 'name', label: 'Name' },
    { key: 'country', label: 'Country' },
    { key: 'sector', label: 'Sector' },
    { key: 'mcap_usd', label: 'Mkt cap', align: 'right', render: (r) => usd(r.mcap_usd) },
  ]
  const ranked: Column[] = [
    { key: 'rank', label: '#', align: 'right', width: 44, render: (r) => r.rank },
    ...base,
    ...meta.pillars.map((p) => ({ key: `p_${p}`, label: p, render: (r: any) => <ScoreBar value={r[`p_${p}`]} width={44} /> })),
    { key: 'composite', label: 'Composite', align: 'right' as const, render: (r: any) => <strong>{r.composite?.toFixed(1)}</strong> },
    ...(showMetrics ? meta.metrics.map((m) => ({
      key: m.key, label: m.label, align: 'right' as const, render: (r: any) => fmtMetric(m.key, r[m.key]),
    })) : []),
  ]
  const excludedCols: Column[] = [
    ...base,
    { key: 'failed', label: 'Failed filters', render: (r) => (
      <span className="chips">{(r.failed as string[]).map((f) => <Badge key={f} tone={f === r.first_failed ? 'bad' : 'neutral'}>{FILTER_SHORT[f] ?? f}</Badge>)}</span>),
    sortValue: (r) => r.failed.length },
    { key: 'roe_median', label: 'ROE 5y', align: 'right', render: (r) => pct(r.roe_median) },
    { key: 'leverage', label: 'ND/EBITDA', align: 'right', render: (r) => fmtMetric('leverage', r.leverage) },
    { key: 'dilution', label: 'Dilution', align: 'right', render: (r) => fmtMetric('dilution', r.dilution) },
    { key: 'receivables_gap', label: 'Recv gap', align: 'right', render: (r) => fmtMetric('receivables_gap', r.receivables_gap) },
  ]
  const finCols: Column[] = [
    { key: 'fin_rank', label: '#', align: 'right', width: 44 },
    ...base,
    { key: 'roe_median', label: 'ROE 5y', align: 'right', render: (r) => pct(r.roe_median) },
    { key: 'roe_spread', label: 'ROE − CoE', align: 'right', render: (r) => fmtMetric('roe_spread', r.roe_spread) },
    { key: 'book_to_price', label: 'Book / price', align: 'right', render: (r) => fmtMetric('book_to_price', r.book_to_price) },
    { key: 'earnings_yield', label: 'Earnings yield', align: 'right', render: (r) => pct(r.earnings_yield) },
    { key: 'fin_composite', label: 'Score', align: 'right', render: (r) => r.fin_composite?.toFixed(1) },
  ]

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1><span className="step-chip">2</span>Screener</h1>
          <p className="lede">Hard filters remove what the process cannot judge or trade. Survivors are ranked 0–100 on each metric
            within their sector and region (winsorised at 1st/99th percentile); pillar scores average the metrics and the composite averages the pillars.</p>
        </div>
      </header>
      <div className="layout-side">
        <aside className="side-panel">
          <Card title="Hard filters">
            <Slider label="Min ADV" value={draft.min_adv_usd} min={0} max={5e6} step={250000} format={usd}
              onChange={(v) => set('min_adv_usd', v)} />
            <Slider label="Min years of statements" value={draft.min_years} min={3} max={8} step={1}
              onChange={(v) => set('min_years', v)} />
            <Slider label="Min years if from Yahoo (non-US)" value={draft.min_years_estimated} min={2} max={8} step={1}
              onChange={(v) => set('min_years_estimated', v)} />
            <Slider label="Positive FCF years (of 5)" value={draft.min_positive_fcf_years} min={0} max={5} step={1}
              onChange={(v) => set('min_positive_fcf_years', v)} />
            <Slider label="Max net debt / EBITDA" value={draft.max_net_debt_ebitda} min={0.5} max={6} step={0.25}
              format={(v) => `${v.toFixed(2)}x`} onChange={(v) => set('max_net_debt_ebitda', v)} />
            <Slider label="Max dilution a year" value={draft.max_dilution} min={0} max={0.15} step={0.005}
              format={(v) => pct(v)} onChange={(v) => set('max_dilution', v)} />
            <Slider label="Max receivables gap" value={draft.max_receivables_gap} min={0} max={0.4} step={0.01}
              format={(v) => pct(v, 0)} onChange={(v) => set('max_receivables_gap', v)} hint="Receivables growth minus sales growth, 3y" />
            <Toggle label="ROE must beat cost of equity" checked={draft.require_roe_above_coe}
              onChange={(v) => set('require_roe_above_coe', v)} />
            <Toggle label="Allow off-benchmark names" checked={draft.allow_off_benchmark}
              onChange={(v) => set('allow_off_benchmark', v)} />
          </Card>
          <Card title="Cost of equity">
            {Object.entries(draft.cost_of_equity).map(([r, v]) => (
              <Slider key={r} label={r} value={v} min={0.04} max={0.14} step={0.0025} format={(x) => pct(x, 2)}
                onChange={(x) => set('cost_of_equity', { ...draft.cost_of_equity, [r]: x })} />
            ))}
          </Card>
          <Card title="Pillar weights">
            {meta.pillars.map((p) => (
              <Slider key={p} label={p} value={draft.pillar_weights[p] ?? 1} min={0} max={3} step={0.25}
                format={(x) => x.toFixed(2)} onChange={(x) => set('pillar_weights', { ...draft.pillar_weights, [p]: x })} />
            ))}
          </Card>
          <div className="side-actions">
            <button className="btn primary" disabled={!dirty} onClick={() => setScreen(draft)}>Apply</button>
            <button className="btn ghost" onClick={() => setDraft(meta.defaults.screen)}>Reset to defaults</button>
          </div>
          {dirty && <p className="muted small">Changes apply to the portfolio and backtest pages too.</p>}
        </aside>
        <div className="content">
          {error && <ErrorBox error={error} />}
          {loading && !data && <Loading />}
          {data && (
            <>
              <Card title={`Funnel · ${data.as_of}`} actions={loading ? <Loading label="Updating" /> : <span className="muted small">Click a step to see who it removed</span>}>
                <Funnel steps={data.funnel} active={tab === 'financials' ? 'financials' : filterKey} onSelect={selectStep} />
              </Card>
              <Card actions={tab === 'ranked' ? <Toggle label="Show raw metrics" checked={showMetrics} onChange={setShowMetrics} /> :
                tab === 'excluded' && filterKey ? <button className="btn ghost" onClick={() => setFilterKey(null)}>Clear: {FILTER_SHORT[filterKey]}</button> : null}
                title={<Tabs value={tab} onChange={(t) => { setTab(t); if (t !== 'excluded') setFilterKey(null) }} tabs={[
                  { key: 'ranked', label: `Ranked (${data.passed.length})` },
                  { key: 'excluded', label: `Excluded (${data.excluded.length})` },
                  { key: 'financials', label: `Financials (${data.financials.length})` },
                ]} />}>
                {tab === 'ranked' && <DataTable rows={data.passed} columns={ranked} onRowClick={(r) => openCompany(r.company_id)}
                  initialSort={{ key: 'rank', dir: 'asc' }} />}
                {tab === 'excluded' && <DataTable rows={excluded} columns={excludedCols} onRowClick={(r) => openCompany(r.company_id)} />}
                {tab === 'financials' && (
                  <>
                    <p className="muted small">Banks and insurers are scored on ROE spread, ROE stability, earnings yield and book-to-price,
                      not on free cash flow. They are kept out of the portfolio unless enabled on the portfolio page.</p>
                    <DataTable rows={data.financials} columns={finCols} onRowClick={(r) => openCompany(r.company_id)}
                      initialSort={{ key: 'fin_rank', dir: 'asc' }} />
                  </>
                )}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
