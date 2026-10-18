// Fixed series colours, legible on both light and dark backgrounds.
// (SVG presentation attributes do not resolve CSS variables, so these are literals.)
export const C = {
  primary: '#2f7ab9',
  secondary: '#e08a3c',
  neutral: '#8a94a6',
  good: '#2e9e6b',
  bad: '#d0544f',
  quint: ['#2e9e6b', '#7cb88f', '#a7adb8', '#e3a07a', '#d0544f'],
}

export const axis = { stroke: '#8a94a6', fontSize: 11 }
export const grid = { stroke: '#8a94a6', strokeOpacity: 0.18 }
export const tooltipStyle = {
  contentStyle: {
    background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12,
    color: 'var(--text)',
  },
  labelStyle: { color: 'var(--text)', fontWeight: 600 },
}
