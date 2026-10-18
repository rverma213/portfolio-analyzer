import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Row } from '../types'

export type Column = {
  key: string
  label: ReactNode
  render?: (row: Row) => ReactNode
  sortValue?: (row: Row) => number | string | null
  align?: 'left' | 'right' | 'center'
  width?: number | string
  title?: string
}

type Props = {
  rows: Row[]
  columns: Column[]
  onRowClick?: (row: Row) => void
  initialSort?: { key: string; dir: 'asc' | 'desc' }
  pageSize?: number
  rowKey?: (row: Row) => string
  selected?: string | null
  empty?: ReactNode
}

export function DataTable({ rows, columns, onRowClick, initialSort, pageSize = 50, rowKey = (r) => r.company_id,
  selected, empty = 'Nothing to show' }: Props) {
  const [sort, setSort] = useState(initialSort ?? null)
  const [limit, setLimit] = useState(pageSize)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    const val = col?.sortValue ?? ((r: Row) => r[sort.key])
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const x = val(a), y = val(b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      return x < y ? -dir : x > y ? dir : 0
    })
  }, [rows, sort, columns])

  const toggle = (key: string) =>
    setSort((s) => (s?.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))

  if (!rows.length) return <div className="empty">{empty}</div>

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: c.align ?? 'left', width: c.width }} title={c.title}
                onClick={() => toggle(c.key)} className={sort?.key === c.key ? 'sorted' : ''}>
                {c.label}
                {sort?.key === c.key && <span className="sort-arrow">{sort.dir === 'asc' ? '▲' : '▼'}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, limit).map((r) => {
            const k = rowKey(r)
            return (
              <tr key={k} onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={`${onRowClick ? 'clickable' : ''} ${selected === k ? 'selected' : ''}`}>
                {columns.map((c) => (
                  <td key={c.key} style={{ textAlign: c.align ?? 'left' }}>
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
      {sorted.length > limit && (
        <button className="btn ghost more" onClick={() => setLimit((l) => l + pageSize * 2)}>
          Show more ({sorted.length - limit} remaining)
        </button>
      )}
    </div>
  )
}
