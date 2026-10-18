import type { ReactNode } from 'react'
import type { FunnelStep } from '../types'

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'good' | 'bad' }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone ?? ''}`}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

export function ScoreBar({ value, width = 64 }: { value: number | null | undefined; width?: number }) {
  if (value == null) return <span className="muted">–</span>
  const v = Math.max(0, Math.min(100, value))
  const hue = v >= 66 ? 'var(--good)' : v >= 33 ? 'var(--accent)' : 'var(--bad)'
  return (
    <span className="scorebar" title={v.toFixed(0)}>
      <span className="scorebar-track" style={{ width }}>
        <span className="scorebar-fill" style={{ width: `${v}%`, background: hue }} />
      </span>
      <span className="scorebar-num">{v.toFixed(0)}</span>
    </span>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'good' | 'bad' | 'warn' | 'neutral' | 'accent' }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

export function PassMark({ pass }: { pass: boolean }) {
  return pass ? <span className="mark good">✓</span> : <span className="mark bad">✗</span>
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <div className="loading"><span className="spinner" />{label}</div>
}

export function ErrorBox({ error }: { error: string }) {
  return <div className="error-box">⚠ {error}</div>
}

export function Card({ title, actions, children, className = '' }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h3>{title}</h3>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function Funnel({ steps, active, onSelect }: { steps: FunnelStep[]; active?: string | null; onSelect?: (key: string | null) => void }) {
  const max = steps[0]?.remaining || 1
  return (
    <div className="funnel">
      {steps.map((s, i) => (
        <div key={s.key} className={`funnel-row ${onSelect && i > 0 ? 'clickable' : ''} ${active === s.key ? 'active' : ''}`}
          onClick={onSelect && i > 0 ? () => onSelect(active === s.key ? null : s.key) : undefined}
          title={i > 0 ? `Click to see the ${s.removed} companies removed here` : undefined}>
          <div className="funnel-label">
            <span className="funnel-step">{i === 0 ? '' : i}</span>{s.label}
          </div>
          <div className="funnel-bar-wrap">
            <div className="funnel-bar" style={{ width: `${(s.remaining / max) * 100}%` }} />
            <span className="funnel-count">{s.remaining.toLocaleString()}</span>
          </div>
          <div className="funnel-removed">{i > 0 && s.removed > 0 ? `−${s.removed.toLocaleString()}` : ''}</div>
        </div>
      ))}
    </div>
  )
}

export function Field({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

type SliderProps = {
  label: ReactNode
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
  format?: (v: number) => string
  hint?: ReactNode
}

export function Slider({ label, value, min, max, step, onChange, format = String, hint }: SliderProps) {
  return (
    <label className="field slider">
      <span className="field-label">
        {label}<span className="field-value">{format(value)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} />
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function Toggle({ label, checked, onChange }: { label: ReactNode; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { key: T; label: ReactNode }[]; value: T; onChange: (k: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={value === t.key}
          className={`tab ${value === t.key ? 'active' : ''}`} onClick={() => onChange(t.key)}>
          {t.label}
        </button>
      ))}
    </div>
  )
}
