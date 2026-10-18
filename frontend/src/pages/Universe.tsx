import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { C, axis, grid, tooltipStyle } from '../components/charts'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Badge, Card, ErrorBox, Loading, Stat, Tabs } from '../components/ui'
import { pct, usd } from '../format'
import { useApp, useAsync } from '../state'
import type { Row } from '../types'

export function Universe() {
  const { asOf, openCompany } = useApp()
  const { data, error, loading } = useAsync(() => api.universe(asOf), [asOf])
  const [mix, setMix] = useState<'by_country' | 'by_sector' | 'by_region'>('by_country')
  const [search, setSearch] = useState('')
  const [region, setRegion] = useState('')
  const [benchOnly, setBenchOnly] = useState(false)

  const rows = useMemo(() => {
    const s = search.trim().toLowerCase()
    return (data?.rows ?? []).filter((r) =>
      (!s || r.name.toLowerCase().includes(s) || r.ticker.toLowerCase().includes(s))
      && (!region || r.region === region) && (!benchOnly || r.in_benchmark))
  }, [data, search, region, benchOnly])

  const columns: Column[] = [
    { key: 'ticker', label: 'Ticker', width: 90 },
    { key: 'name', label: 'Name' },
    { key: 'country', label: 'Country' },
    { key: 'sector', label: 'Sector' },
    { key: 'mcap_usd', label: 'Mkt cap', align: 'right', render: (r) => usd(r.mcap_usd) },
    { key: 'adv_usd', label: 'ADV', align: 'right', render: (r) => usd(r.adv_usd), title: '20-day average daily value traded' },
    { key: 'bench_weight', label: 'Bench wt', align: 'right', render: (r) => pct(r.bench_weight, 2) },
    { key: 'in_benchmark', label: 'Status', render: (r) => (r.in_benchmark ? <Badge>Benchmark</Badge> : <Badge tone="warn">Off-benchmark</Badge>), sortValue: (r) => (r.in_benchmark ? 1 : 0) },
    { key: 'n_years', label: 'Years filed', align: 'right' },
  ]

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1><span className="step-chip">1</span>Universe</h1>
          <p className="lede">MSCI World Small Cap constituents (in production: reconstructed from the iShares WSML daily holdings file),
            plus developed-market small caps outside the index such as recent IPOs. Benchmark weights are by market cap.</p>
        </div>
      </header>
      {error && <ErrorBox error={error} />}
      {loading && !data && <Loading />}
      {data && (
        <>
          <div className="stats">
            <Stat label="Listed companies" value={data.summary.companies.toLocaleString()} sub={`as of ${data.as_of}`} />
            <Stat label="Benchmark members" value={data.summary.benchmark.toLocaleString()} />
            <Stat label="Median market cap" value={usd(data.summary.median_mcap)} />
            <Stat label="Total market cap" value={usd(data.summary.total_mcap)} />
          </div>
          <Card title="Benchmark mix" actions={
            <Tabs value={mix} onChange={setMix} tabs={[
              { key: 'by_country', label: 'Country' }, { key: 'by_sector', label: 'Sector' }, { key: 'by_region', label: 'Region' }]} />}>
            <ResponsiveContainer width="100%" height={mix === 'by_region' ? 180 : 320}>
              <BarChart data={data[mix].filter((r: Row) => r.bench_weight > 0)} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid {...grid} horizontal={false} />
                <XAxis type="number" tick={axis} tickFormatter={(v) => pct(v, 0)} />
                <YAxis type="category" dataKey={mix.replace('by_', '')} tick={axis} width={150} interval={0} />
                <Tooltip {...tooltipStyle} formatter={(v: any, n: any) => (n === 'Benchmark weight' ? pct(v) : v)} />
                <Bar isAnimationActive={false} dataKey="bench_weight" name="Benchmark weight" fill={C.primary} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title={`Companies (${rows.length.toLocaleString()})`} actions={
            <div className="filters-inline">
              <input placeholder="Search name or ticker" value={search} onChange={(e) => setSearch(e.target.value)} />
              <select value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="">All regions</option>
                {data.by_region.map((r) => <option key={r.region}>{r.region}</option>)}
              </select>
              <label className="toggle"><input type="checkbox" checked={benchOnly} onChange={(e) => setBenchOnly(e.target.checked)} /> Benchmark only</label>
            </div>}>
            <DataTable rows={rows} columns={columns} onRowClick={(r) => openCompany(r.company_id)}
              initialSort={{ key: 'mcap_usd', dir: 'desc' }} />
          </Card>
        </>
      )}
    </div>
  )
}
