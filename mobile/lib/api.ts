import type {
  BatterStats,
  FormGame,
  Game,
  H2H,
  NBAPlayerStats,
  PitcherStats,
  PlayerProjection,
  Prediction,
  Sport,
  Standing,
  TeamForm,
  TopPerformers,
} from './types';

// Change this to your local IP when testing on a physical device
// e.g. 'http://192.168.1.100:8000'
export const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

const enc = encodeURIComponent;

export const api = {
  health: () => get<{ status: string }>('/health'),

  teams: (league: Sport) =>
    get<string[]>(`/teams?league=${league}`),

  games: (league: Sport, team = '', limit = 30) =>
    get<Game[]>(`/games?league=${league}&team=${enc(team)}&limit=${limit}`),

  standings: (league: Sport) =>
    get<Standing[]>(`/standings?league=${league}`),

  teamForm: (league: Sport, team: string, n = 15) =>
    get<TeamForm>(`/team/form?league=${league}&team=${enc(team)}&n=${n}`),

  h2h: (league: Sport, teamA: string, teamB: string, n = 10) =>
    get<H2H>(`/team/h2h?league=${league}&team_a=${enc(teamA)}&team_b=${enc(teamB)}&n=${n}`),

  homeAway: (league: Sport, team: string) =>
    get<unknown>(`/team/home-away?league=${league}&team=${enc(team)}`),

  prediction: (league: Sport, teamA: string, teamB: string, home = '') =>
    get<Prediction>(`/team/prediction?league=${league}&team_a=${enc(teamA)}&team_b=${enc(teamB)}&home=${enc(home)}`),

  topPerformers: (league: Sport, team: string, n = 15) =>
    get<TopPerformers>(`/team/top-performers?league=${league}&team=${enc(team)}&n=${n}`),

  players: (league: Sport, opts: { team?: string; name?: string; role?: string } = {}) =>
    get<string[]>(
      `/players?league=${league}&team=${enc(opts.team ?? '')}&name=${enc(opts.name ?? '')}&role=${enc(opts.role ?? '')}`
    ),

  playerStats: (league: Sport, name: string, n = 15, role = 'batter') =>
    get<NBAPlayerStats | BatterStats | PitcherStats>(
      `/player/stats?league=${league}&name=${enc(name)}&n=${n}&role=${role}`
    ),

  playerVsTeam: (league: Sport, name: string, opponent: string, n = 15, role = 'batter') =>
    get<unknown>(
      `/player/vs-team?league=${league}&name=${enc(name)}&opponent=${enc(opponent)}&n=${n}&role=${role}`
    ),

  playerLog: (league: Sport, name: string, n = 20, role = 'batter') =>
    get<unknown[]>(`/player/log?league=${league}&name=${enc(name)}&n=${n}&role=${role}`),

  playerProjected: (name: string, opponent: string, n = 15) =>
    get<PlayerProjection>(`/player/projected?name=${enc(name)}&opponent=${enc(opponent)}&n=${n}`),

  scrapeTeam: (league: Sport, team: string, last = 15, season = 2025) =>
    post<{ games_added: number; players_added: number }>('/scrape/team', {
      league,
      team,
      last,
      season,
    }),

  aiChat: (league: Sport, message: string, history: { role: string; content: string }[] = []) =>
    post<{ response: string }>('/ai/chat', { league, message, history }),
};
