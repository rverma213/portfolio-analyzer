import { useMemo, useRef, useState } from 'react'
import { usd } from '../format'
import type { StockOption } from '../types'

const MAX_SHOWN = 60

// Searchable dropdown over every company: type part of a ticker or name, then pick.
export function StockPicker({ options, value, onChange }: { options: StockOption[]; value: string | null; onChange: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const listRef = useRef<HTMLUListElement>(null)
  const selected = options.find((o) => o.company_id === value)

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return [...options].sort((a, b) => (b.mcap_usd ?? 0) - (a.mcap_usd ?? 0)).slice(0, MAX_SHOWN)
    const score = (o: StockOption) => {
      const t = o.ticker.toLowerCase()
      const n = o.name.toLowerCase()
      if (t === q) return 0
      if (t.startsWith(q)) return 1
      if (n.startsWith(q)) return 2
      if (n.includes(q) || t.includes(q)) return 3
      return -1
    }
    return options.map((o) => [score(o), o] as const).filter(([s]) => s >= 0)
      .sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name)).slice(0, MAX_SHOWN).map(([, o]) => o)
  }, [options, query])

  const pick = (o: StockOption) => {
    onChange(o.company_id)
    setOpen(false)
    setQuery('')
  }
  const move = (i: number) => {
    setActive(i)
    listRef.current?.children[i]?.scrollIntoView({ block: 'nearest' })
  }

  return (
    <div className="picker">
      <input id="stock-picker" role="combobox" aria-expanded={open} aria-controls="stock-picker-list"
        aria-label="Choose a stock" autoComplete="off" spellCheck={false}
        placeholder={selected ? `${selected.ticker} · ${selected.name}` : 'Search ticker or company name'}
        value={open ? query : selected ? `${selected.ticker} · ${selected.name}` : ''}
        onFocus={(e) => { setOpen(true); setActive(0); e.target.select() }}
        onBlur={() => setOpen(false)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0) }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); move(Math.min(active + 1, matches.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); move(Math.max(active - 1, 0)) }
          else if (e.key === 'Enter' && matches[active]) { e.preventDefault(); pick(matches[active]); e.currentTarget.blur() }
          else if (e.key === 'Escape') { setOpen(false); e.currentTarget.blur() }
        }} />
      <span className="picker-caret" aria-hidden>▾</span>
      {open && (
        <ul className="picker-list" id="stock-picker-list" role="listbox" ref={listRef}>
          {matches.length === 0 && <li className="picker-empty">No company matches “{query}”</li>}
          {matches.map((o, i) => (
            <li key={o.company_id} role="option" aria-selected={o.company_id === value}
              className={`${i === active ? 'active' : ''} ${o.company_id === value ? 'selected' : ''}`}
              onMouseDown={(e) => { e.preventDefault(); pick(o) }} onMouseEnter={() => setActive(i)}>
              <span className="picker-ticker">{o.ticker}</span>
              <span className="picker-name">{o.name}</span>
              <span className="picker-meta">{o.country} · {o.sector} · {usd(o.mcap_usd)}</span>
            </li>
          ))}
          {!query && <li className="picker-empty">Largest {MAX_SHOWN} by market cap. Type to search all {options.length.toLocaleString()}.</li>}
        </ul>
      )}
    </div>
  )
}
