import { useEffect, useRef, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, type PlayerSeason, type SearchHit, type SimilarPlayer } from '../lib/api'
import { Card, ErrorNote, Loading, StatTile, chartInk } from '../components/ui'

const TREND_SERIES = [
  { key: 'pts_pg', name: 'Points', color: 'var(--series-1)' },
  { key: 'reb_pg', name: 'Rebounds', color: 'var(--series-2)' },
  { key: 'ast_pg', name: 'Assists', color: 'var(--series-3)' },
] as const

export default function Players() {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [selected, setSelected] = useState<SearchHit | null>(null)
  const [seasons, setSeasons] = useState<PlayerSeason[] | null>(null)
  const [similar, setSimilar] = useState<SimilarPlayer[] | null>(null)
  const [error, setError] = useState('')
  const debounce = useRef<ReturnType<typeof setTimeout>>(null)

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current)
    if (query.trim().length < 2) {
      setHits([])
      return
    }
    debounce.current = setTimeout(() => {
      api.searchPlayers(query.trim()).then(setHits).catch(() => setHits([]))
    }, 250)
  }, [query])

  function pick(hit: SearchHit) {
    setSelected(hit)
    setHits([])
    setQuery(hit.player_name)
    setSeasons(null)
    setSimilar(null)
    setError('')
    api.player(hit.player_id).then((d) => setSeasons(d.seasons)).catch((e) => setError(e.message))
    api.similar(hit.player_id).then((d) => setSimilar(d.similar)).catch(() => setSimilar([]))
  }

  const latest = seasons?.[seasons.length - 1]

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Player explorer</h1>

      <div className="relative max-w-md">
        <input
          className="card w-full px-3 py-2 text-sm"
          placeholder="Search players — try “jokic” or “doncic”…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search players"
        />
        {hits.length > 0 && (
          <ul className="card absolute z-10 mt-1 w-full p-1">
            {hits.map((h) => (
              <li key={h.player_id}>
                <button
                  className="w-full rounded px-2 py-1.5 text-left text-sm hover:bg-[var(--page)]"
                  onClick={() => pick(h)}
                >
                  {h.player_name}
                  <span className="ml-2 text-xs text-[var(--text-muted)]">{h.latest_season}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <ErrorNote message={error} />}
      {selected && !seasons && !error && <Loading />}

      {latest && seasons && (
        <>
          <div className="flex flex-wrap gap-3">
            <StatTile label="Points / game" value={latest.pts_pg.toFixed(1)} sub={latest.season} />
            <StatTile label="Rebounds / game" value={latest.reb_pg.toFixed(1)} sub={latest.season} />
            <StatTile label="Assists / game" value={latest.ast_pg.toFixed(1)} sub={latest.season} />
            <StatTile label="True shooting" value={`${(latest.ts_pct * 100).toFixed(1)}%`} sub={latest.season} />
            <StatTile label="Usage" value={`${(latest.usg_pct * 100).toFixed(1)}%`} sub={latest.season} />
          </div>

          <Card title={`${selected!.player_name} — per-game trend`}>
            <div className="h-72">
              <ResponsiveContainer>
                <LineChart data={seasons} margin={{ top: 8, right: 24, bottom: 4, left: 0 }}>
                  <CartesianGrid stroke={chartInk.grid} vertical={false} />
                  <XAxis
                    dataKey="season"
                    tick={{ fill: chartInk.axis, fontSize: 11 }}
                    tickLine={false} axisLine={{ stroke: 'var(--baseline)' }}
                  />
                  <YAxis
                    tick={{ fill: chartInk.axis, fontSize: 11 }}
                    tickLine={false} axisLine={false} width={32}
                  />
                  <Tooltip contentStyle={chartInk.tooltip} />
                  <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
                  {TREND_SERIES.map((s) => (
                    <Line
                      key={s.key} type="monotone" dataKey={s.key} name={s.name}
                      stroke={s.color} strokeWidth={2}
                      dot={{ r: 4, fill: s.color, strokeWidth: 0 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card title="Statistically similar players (ML)">
            {!similar ? (
              <Loading />
            ) : similar.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">
                No qualified profile (needs 20+ games, 15+ min/game).
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {similar.map((s) => (
                  <div key={s.player_id} className="rounded-lg border border-[var(--border)] p-3">
                    <div className="flex items-baseline justify-between">
                      <span className="text-sm font-medium">{s.player_name}</span>
                      <span className="text-xs text-[var(--text-muted)]">{s.team}</span>
                    </div>
                    <div className="tabular mt-1 text-xs text-[var(--text-secondary)]">
                      {s.pts_pg.toFixed(1)} pts · {s.reb_pg.toFixed(1)} reb · {s.ast_pg.toFixed(1)} ast
                    </div>
                    <div className="mt-2 h-1.5 rounded bg-[var(--grid)]">
                      <div
                        className="h-1.5 rounded bg-[var(--series-1)]"
                        style={{ width: `${Math.max(0, s.similarity) * 100}%` }}
                      />
                    </div>
                    <div className="mt-1 text-right text-xs text-[var(--text-muted)]">
                      similarity {s.similarity.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
