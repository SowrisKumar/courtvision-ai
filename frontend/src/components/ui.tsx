import type { ReactNode } from 'react'

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="card">
      {title && (
        <h2 className="mb-3 text-sm font-semibold tracking-wide text-[var(--text-secondary)] uppercase">
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}

export function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card min-w-28">
      <div className="text-xs text-[var(--text-muted)]">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-[var(--text-secondary)]">{sub}</div>}
    </div>
  )
}

export function Loading() {
  return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
}

export function ErrorNote({ message }: { message: string }) {
  return <p className="p-4 text-sm text-[var(--series-2)]">⚠ {message}</p>
}

export function SeasonSelect({
  seasons,
  value,
  onChange,
}: {
  seasons: string[]
  value: string
  onChange: (s: string) => void
}) {
  return (
    <select
      className="card cursor-pointer px-3 py-1.5 text-sm"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Season"
    >
      {seasons.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  )
}

export const chartInk = {
  grid: 'var(--grid)',
  axis: 'var(--text-muted)',
  tooltip: {
    backgroundColor: 'var(--surface-1)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text-primary)',
    fontSize: 12,
  },
}
