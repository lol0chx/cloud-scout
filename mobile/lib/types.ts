export type Sport = 'NBA' | 'MLB';

export interface Game {
  id: number;
  date: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  league: string;
  season: string;
}

export interface Standing {
  Team: string;
  W: number;
  L: number;
  GP: number;
  'Win%': number;
  'Avg Pts': number;
  'Avg Allowed': number;
  'Net Rtg': number;
  Streak: string;
}

export interface TeamForm {
  team: string;
  games: number;
  streak_count: number;
  streak_type: string;
  avg_scored: number;
  avg_conceded: number;
  net_rating: number;
  form_log: FormGame[];
}

export interface FormGame {
  date: string;
  location: string;
  opponent: string;
  result: string;
  scored: number;
  conceded: number;
  margin: number;
  rolling_avg: number;
}

export interface Prediction {
  team_a: string;
  team_b: string;
  prob_a: number;
  prob_b: number;
  margin: number;
  team_a_record: { wins: number; losses: number; win_pct: number };
  team_b_record: { wins: number; losses: number; win_pct: number };
  team_a_streak: { count: number; type: string };
  team_b_streak: { count: number; type: string };
}

export interface H2H {
  games: Record<string, unknown>[];
  team_a_wins: number;
  team_b_wins: number;
  avg_total: number;
}

export interface NBAPlayerStats {
  player: string;
  games: number;
  points: number;
  assists: number;
  rebounds: number;
  steals: number;
  blocks: number;
}

export interface BatterStats {
  player: string;
  games: number;
  AVG: number;
  HR: number;
  RBI: number;
  H: number;
  R: number;
  BB: number;
  SO: number;
}

export interface PitcherStats {
  player: string;
  games: number;
  ERA: number;
  WHIP: number;
  IP: number;
  SO: number;
  BB: number;
  H: number;
  HR: number;
}

export interface TopPerformers {
  players?: { player: string; avg_points: number; avg_assists: number; avg_rebounds: number; games: number }[];
  batters?: { player: string; AVG: number; HR: number; RBI: number; games: number }[];
  pitchers?: { player: string; ERA: number; WHIP: number; IP: number; SO: number; games: number }[];
}

export interface StatBreakdown {
  season_avg: number;
  base_avg_decayed: number;
  recent_avg_5g: number;
  h2h_avg_raw: number | null;
  h2h_avg_shrunk: number | null;
  h2h_games: number;
  h2h_weight_pct: number;
  def_factor: number;
  min_factor: number;
  projected: number;
}

export interface PlayerProjection {
  player: string;
  team: string;
  opponent: string;
  projected: {
    points: number;
    assists: number;
    rebounds: number;
    steals: number;
  };
  breakdown: {
    points: StatBreakdown;
    assists: StatBreakdown;
    rebounds: StatBreakdown;
    steals: StatBreakdown;
  };
  h2h_games: number;
  h2h_log: Record<string, unknown>[];
  season_games_used: number;
  recent_minutes: number;
  season_minutes: number;
  minutes_trend: number;
  streak_context: 'hot' | 'cold' | 'normal';
  injury_status: string | null;
  injury_detail: string | null;
  confidence: 'high' | 'medium' | 'low';
}
