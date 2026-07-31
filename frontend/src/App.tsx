import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { api } from './lib/api'
import { ErrorNote, Loading } from './components/ui'
import League from './pages/League'
import Players from './pages/Players'
import Leaderboards from './pages/Leaderboards'
import Predict from './pages/Predict'

const NAV = [
  { to: '/', label: 'League' },
  { to: '/players', label: 'Players' },
  { to: '/leaderboards', label: 'Leaderboards' },
  { to: '/predict', label: 'Predict' },
]

export default function App() {
  const [seasons, setSeasons] = useState<string[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.health().then((h) => setSeasons(h.seasons)).catch((e) => setError(e.message))
  }, [])

  return (
    <div className="mx-auto max-w-5xl px-4 pb-16">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="text-lg font-bold">
          🏀 CourtVision <span className="text-[var(--series-1)]">AI</span>
        </div>
        <nav className="flex gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm ${
                  isActive
                    ? 'bg-[var(--surface-1)] font-semibold text-[var(--text-primary)] border border-[var(--border)]'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {error ? (
        <ErrorNote message={`API unreachable: ${error}. Is the backend running on port 8000?`} />
      ) : !seasons ? (
        <Loading />
      ) : (
        <Routes>
          <Route path="/" element={<League seasons={seasons} />} />
          <Route path="/players" element={<Players seasons={seasons} />} />
          <Route path="/leaderboards" element={<Leaderboards seasons={seasons} />} />
          <Route path="/predict" element={<Predict seasons={seasons} />} />
        </Routes>
      )}
    </div>
  )
}
