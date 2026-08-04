import { useEffect, useState } from 'react'
import {
  CartesianGrid, LabelList, Scatter, ScatterChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, type TeamSeason } from '../lib/api'
import { Card, ErrorNote, Loading, SeasonSelect, chartInk } from '../components/ui'

export default function League({ seasons }: { seasons: string[] }) {
  const [season, setSeason] = useState(seasons[seasons.length - 1])
  const [teams, setTeams] = useState<TeamSeason[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setTeams(null)
    setError('')  // otherwise one transient failure blanks the page until reload
    api.teams(season).then(setTeams).catch((e) => setError(e.message))
  }, [season])

  if (error) return <ErrorNote message={error} />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">League overview</h1>
        <SeasonSelect seasons={seasons} value={season} onChange={setSeason} />
      </div>

      {!teams ? (
        <Loading />
      ) : (
        <>
          <Card title={`Team efficiency landscape, ${season}`}>
            <p className="mb-2 text-xs text-[var(--text-muted)]">
              Offensive vs defensive rating (points per 100 possessions). Down-right is good.
            </p>
            <div className="h-105">
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
                  <CartesianGrid stroke={chartInk.grid} strokeWidth={1} />
                  <XAxis
                    type="number" dataKey="off_rating" name="Offensive rating"
                    domain={['dataMin - 1', 'dataMax + 1']}
                    tick={{ fill: chartInk.axis, fontSize: 11 }}
                    tickLine={false} axisLine={{ stroke: 'var(--baseline)' }}
                    label={{ value: 'Offensive rating →', position: 'insideBottom', offset: -4, fill: chartInk.axis, fontSize: 11 }}
                  />
                  <YAxis
                    type="number" dataKey="def_rating" name="Defensive rating"
                    domain={['dataMin - 1', 'dataMax + 1']} reversed
                    tick={{ fill: chartInk.axis, fontSize: 11 }}
                    tickLine={false} axisLine={{ stroke: 'var(--baseline)' }}
                    label={{ value: 'Defensive rating (lower is better)', angle: -90, position: 'insideLeft', fill: chartInk.axis, fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={chartInk.tooltip}
                    formatter={(v) => (typeof v === 'number' ? v.toFixed(1) : v)}
                    labelFormatter={() => ''}
                  />
                  <Scatter data={teams} fill="var(--series-1)">
                    <LabelList dataKey="team" position="top" style={{ fill: 'var(--text-secondary)', fontSize: 10 }} />
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card title="Standings">
            <div className="overflow-x-auto">
              <table className="tabular w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--text-muted)]">
                    <th className="py-1 pr-3">#</th>
                    <th className="py-1 pr-3">Team</th>
                    <th className="py-1 pr-3 text-right">W</th>
                    <th className="py-1 pr-3 text-right">L</th>
                    <th className="py-1 pr-3 text-right">Win%</th>
                    <th className="py-1 pr-3 text-right">ORtg</th>
                    <th className="py-1 pr-3 text-right">DRtg</th>
                    <th className="py-1 pr-3 text-right">Net</th>
                    <th className="py-1 pr-3 text-right">Pace</th>
                  </tr>
                </thead>
                <tbody>
                  {teams.map((t, i) => (
                    <tr key={t.team_id} className="border-t border-[var(--border)]">
                      <td className="py-1 pr-3 text-[var(--text-muted)]">{i + 1}</td>
                      <td className="py-1 pr-3">{t.team_name}</td>
                      <td className="py-1 pr-3 text-right">{t.w}</td>
                      <td className="py-1 pr-3 text-right">{t.l}</td>
                      <td className="py-1 pr-3 text-right">{t.win_pct.toFixed(3)}</td>
                      <td className="py-1 pr-3 text-right">{t.off_rating.toFixed(1)}</td>
                      <td className="py-1 pr-3 text-right">{t.def_rating.toFixed(1)}</td>
                      <td className="py-1 pr-3 text-right">{t.net_rating.toFixed(1)}</td>
                      <td className="py-1 pr-3 text-right">{t.pace.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
