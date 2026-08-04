import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, type LeaderRow } from '../lib/api'
import { Card, ErrorNote, Loading, SeasonSelect, chartInk } from '../components/ui'

const STATS = [
  { key: 'pts_pg', label: 'Points / game', fmt: (v: number) => v.toFixed(1) },
  { key: 'reb_pg', label: 'Rebounds / game', fmt: (v: number) => v.toFixed(1) },
  { key: 'ast_pg', label: 'Assists / game', fmt: (v: number) => v.toFixed(1) },
  { key: 'ts_pct', label: 'True shooting %', fmt: (v: number) => `${(v * 100).toFixed(1)}%` },
  { key: 'usg_pct', label: 'Usage %', fmt: (v: number) => `${(v * 100).toFixed(1)}%` },
  { key: 'pie', label: 'PIE', fmt: (v: number) => v.toFixed(3) },
] as const

export default function Leaderboards({ seasons }: { seasons: string[] }) {
  const [season, setSeason] = useState(seasons[seasons.length - 1])
  const [stat, setStat] = useState<(typeof STATS)[number]>(STATS[0])
  const [rows, setRows] = useState<LeaderRow[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setRows(null)
    setError('')  // otherwise one transient failure blanks the page until reload
    api.leaderboard(stat.key, season).then(setRows).catch((e) => setError(e.message))
  }, [stat, season])

  if (error) return <ErrorNote message={error} />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Leaderboards</h1>
        <div className="flex gap-2">
          <select
            className="card cursor-pointer px-3 py-1.5 text-sm"
            value={stat.key}
            onChange={(e) => setStat(STATS.find((s) => s.key === e.target.value) ?? STATS[0])}
            aria-label="Stat"
          >
            {STATS.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
          <SeasonSelect seasons={seasons} value={season} onChange={setSeason} />
        </div>
      </div>

      {!rows ? (
        <Loading />
      ) : (
        <Card title={`${stat.label}, ${season} (min. 40 games)`}>
          <div style={{ height: rows.length * 34 + 40 }}>
            <ResponsiveContainer>
              <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 8 }} barCategoryGap={2}>
                <CartesianGrid stroke={chartInk.grid} horizontal={false} />
                <XAxis
                  type="number" domain={[0, 'dataMax']} hide
                />
                <YAxis
                  type="category" dataKey="player_name" width={170}
                  tick={{ fill: 'var(--text-primary)', fontSize: 12 }}
                  tickLine={false} axisLine={{ stroke: 'var(--baseline)' }}
                />
                <Tooltip
                  contentStyle={chartInk.tooltip}
                  formatter={(v) => stat.fmt(v as number)}
                  cursor={{ fill: 'var(--grid)', opacity: 0.4 }}
                />
                <Bar dataKey={stat.key} name={stat.label} fill="var(--series-1)" radius={[0, 4, 4, 0]} barSize={18}>
                  <LabelList
                    dataKey={stat.key} position="right"
                    formatter={(v: unknown) => stat.fmt(v as number)}
                    style={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  )
}
