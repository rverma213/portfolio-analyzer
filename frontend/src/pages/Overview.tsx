import { Link } from 'react-router-dom'
import { api } from '../api'
import { Card, ErrorBox, Funnel, Loading } from '../components/ui'
import { num } from '../format'
import { useApp, useAsync } from '../state'

const ROUTES: Record<string, string> = {
  universe: '/universe', screener: '/screener', portfolio: '/portfolio', backtest: '/backtest',
}

const WHAT: Record<string, string> = {
  universe: 'Benchmark constituents plus eligible off-benchmark developed small caps, rebuilt each month.',
  screener: 'Ten hard filters remove what the process cannot judge or trade, then four pillars rank the rest within sector and region.',
  portfolio: '40–80 names sized by conviction, capped by position, liquidity, sector and country limits.',
  backtest: 'Point-in-time test of the screen (quintiles by region) and of the full process against the benchmark.',
}

export function Overview() {
  const { asOf } = useApp()
  const { data, error, loading } = useAsync(() => api.pipeline(asOf), [asOf])
  const stages = (data?.stages ?? []).filter((s) => s.key in ROUTES)

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>From universe to portfolio</h1>
          <p className="lede">
            The portfolio owns 40–80 small companies that turn earnings into cash, earn a high and stable return on equity
            above their cost of capital, and trade at a reasonable free-cash-flow yield. Each step below is a page.
          </p>
        </div>
      </header>
      {error && <ErrorBox error={error} />}
      {loading && !data && <Loading />}
      {data && (
        <>
          <div className="pipeline">
            {stages.map((s, i) => (
              <Link key={s.key} to={ROUTES[s.key]} className="pipe-card">
                <div className="pipe-n">{i + 1}</div>
                <div className="pipe-label">{s.label}</div>
                <div className="pipe-count">
                  {s.key === 'backtest' ? (s.count == null ? '—' : `IR ${num(s.count, 2)}`) : s.count?.toLocaleString()}
                </div>
                <div className="pipe-detail">{s.detail}</div>
                <p className="pipe-what">{WHAT[s.key]}</p>
                {i < stages.length - 1 && <span className="pipe-arrow" aria-hidden>→</span>}
              </Link>
            ))}
          </div>
          <div className="grid-2">
            <Card title={`Hard-filter funnel · ${data.as_of}`} actions={<Link to="/screener" className="btn ghost">Open screener</Link>}>
              <Funnel steps={data.funnel} />
            </Card>
            <Card title="How a share price rises, and what the process looks for">
              <ul className="bullets">
                <li><strong>Fundamentals compound.</strong> Value grows with earnings and cash flow only when reinvested profit earns more than the cost of equity — hence the ROE ≥ CoE filter.</li>
                <li><strong>Cash, not just earnings.</strong> FCF conversion, accruals and the receivables-vs-sales gap check that profit is real.</li>
                <li><strong>Returns that last.</strong> ROE level and stability, cross-checked with ROIC so leverage cannot flatter the result.</li>
                <li><strong>A safe balance sheet, no dilution.</strong> Net debt / EBITDA below 3x; share count growing no more than 5% a year.</li>
                <li><strong>A sensible price.</strong> Earnings and FCF yields are part of the score: a good company is not always a good investment.</li>
              </ul>
              <p className="muted small">Source: CFA Level II equity valuation readings.</p>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
