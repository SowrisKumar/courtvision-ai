import { useEffect, useState } from 'react'
import { api, type Prediction, type TeamSeason } from '../lib/api'
import { Card, ErrorNote, Loading, StatTile } from '../components/ui'

const MODEL_LABELS: Record<string, string> = {
  logistic_regression: 'Logistic regression',
  hist_gradient_boosting: 'Gradient boosting',
}

// Declared at module scope on purpose: defined inside Predict it would be a new
// component type on every render, remounting both selects and dropping focus.
function TeamPicker({
  label,
  value,
  teams,
  onChange,
}: {
  label: string
  value: number | null
  teams: TeamSeason[]
  onChange: (id: number) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
      {label}
      <select
        className="card cursor-pointer px-3 py-1.5 text-sm text-[var(--text-primary)]"
        value={value ?? ''}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {teams.map((t) => (
          <option key={t.team_id} value={t.team_id}>{t.team_name}</option>
        ))}
      </select>
    </label>
  )
}

export default function Predict({ seasons }: { seasons: string[] }) {
  const [teams, setTeams] = useState<TeamSeason[]>([])
  const [homeId, setHomeId] = useState<number | null>(null)
  const [awayId, setAwayId] = useState<number | null>(null)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const latest = seasons[seasons.length - 1]

  useEffect(() => {
    api.teams(latest).then((t) => {
      const sorted = [...t].sort((a, b) => a.team_name.localeCompare(b.team_name))
      setTeams(sorted)
      setHomeId(sorted[0]?.team_id ?? null)
      setAwayId(sorted[1]?.team_id ?? null)
    }).catch((e) => setError(e.message))
  }, [latest])

  useEffect(() => {
    if (homeId == null || awayId == null || homeId === awayId) {
      setPrediction(null)
      return
    }
    setLoading(true)
    setError('')
    api.predict(homeId, awayId)
      .then(setPrediction)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [homeId, awayId])

  const pct = prediction ? Math.round(prediction.home_win_probability * 1000) / 10 : null

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Game predictor</h1>
      <p className="max-w-xl text-sm text-[var(--text-secondary)]">
        Pregame win probability from each team's current form (last-10 record and margin,
        season record, rest).
        {prediction && (
          <>
            {' '}
            {MODEL_LABELS[prediction.model] ?? prediction.model}, AUC{' '}
            {prediction.model_auc.toFixed(2)} on {prediction.model_test_season}, a season
            held out of training.
          </>
        )}
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <TeamPicker label="Home team" value={homeId} teams={teams} onChange={setHomeId} />
        <span className="pb-2 text-sm text-[var(--text-muted)]">vs</span>
        <TeamPicker label="Away team" value={awayId} teams={teams} onChange={setAwayId} />
      </div>

      {homeId === awayId && homeId != null && (
        <p className="text-sm text-[var(--text-muted)]">Pick two different teams.</p>
      )}
      {error && <ErrorNote message={error} />}
      {loading && <Loading />}

      {prediction && pct != null && (
        <>
          <Card title={`Home win probability, as of ${prediction.as_of_season}`}>
            <div className="mb-1 flex justify-between text-sm font-medium">
              <span>{prediction.home.team} (home)</span>
              <span>{prediction.away.team}</span>
            </div>
            <div
              className="flex h-6 overflow-hidden rounded"
              role="img"
              aria-label={`${prediction.home.team} ${pct}%, ${prediction.away.team} ${(100 - pct).toFixed(1)}%`}
            >
              <div className="bg-[var(--series-1)]" style={{ width: `${pct}%` }} />
              <div className="w-0.5 bg-[var(--surface-1)]" />
              <div className="flex-1 bg-[var(--series-2)]" />
            </div>
            <div className="tabular mt-1 flex justify-between text-sm text-[var(--text-secondary)]">
              <span>{pct.toFixed(1)}%</span>
              <span>{(100 - pct).toFixed(1)}%</span>
            </div>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2">
            {[prediction.home, prediction.away].map((f, i) => (
              <Card key={f.team} title={`${f.team} ${i === 0 ? '(home)' : '(away)'}: current form`}>
                <div className="flex flex-wrap gap-3">
                  <StatTile label="Last 10 win%" value={(f.form_win_pct * 100).toFixed(0) + '%'} />
                  <StatTile
                    label="Last 10 margin"
                    value={`${f.form_margin > 0 ? '+' : ''}${f.form_margin.toFixed(1)}`}
                  />
                  <StatTile label="Season win%" value={(f.season_win_pct * 100).toFixed(0) + '%'} />
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
