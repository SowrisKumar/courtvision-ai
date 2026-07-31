// Typed client for the CourtVision API (proxied under /api in dev/preview).

const BASE = '/api'

export interface TeamSeason {
  team_id: number
  team_name: string
  team: string
  season: string
  gp: number
  w: number
  l: number
  win_pct: number
  pts_pg: number
  off_rating: number
  def_rating: number
  net_rating: number
  pace: number
  ts_pct: number
}

export interface PlayerSeason {
  player_id: number
  player_name: string
  team: string
  season: string
  gp: number
  min_pg: number
  pts_pg: number
  reb_pg: number
  ast_pg: number
  ts_pct: number
  usg_pct: number
  net_rating: number
}

export interface SearchHit {
  player_id: number
  player_name: string
  latest_season: string
}

export interface SimilarPlayer {
  player_id: number
  player_name: string
  team: string
  similarity: number
  pts_pg: number
  reb_pg: number
  ast_pg: number
  ts_pct: number
  usg_pct: number
}

export interface LeaderRow {
  player_id: number
  player_name: string
  team: string
  season: string
  gp: number
  min_pg: number
  [stat: string]: number | string
}

export interface TeamForm {
  team: string
  season: string
  form_win_pct: number
  form_margin: number
  season_win_pct: number
}

export interface Prediction {
  home: TeamForm
  away: TeamForm
  home_win_probability: number
  model: string
  as_of_season: string
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  health: () => get<{ status: string; seasons: string[] }>('/health'),
  teams: (season: string) => get<TeamSeason[]>(`/teams?season=${season}`),
  searchPlayers: (q: string) =>
    get<SearchHit[]>(`/players/search?q=${encodeURIComponent(q)}`),
  player: (id: number) =>
    get<{ player_id: number; player_name: string; seasons: PlayerSeason[] }>(`/players/${id}`),
  similar: (id: number, limit = 6) =>
    get<{ season: string; similar: SimilarPlayer[] }>(`/players/${id}/similar?limit=${limit}`),
  leaderboard: (stat: string, season: string, limit = 12) =>
    get<LeaderRow[]>(`/leaderboards/${stat}?season=${season}&limit=${limit}`),
  predict: (homeId: number, awayId: number) =>
    get<Prediction>(`/predict/game?home_team_id=${homeId}&away_team_id=${awayId}`),
}
