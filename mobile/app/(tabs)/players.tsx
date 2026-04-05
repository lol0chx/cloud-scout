import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import SportSelector from '../../components/SportSelector';
import TeamPicker from '../../components/TeamPicker';
import { api } from '../../lib/api';
import { C, S } from '../../lib/theme';
import type { PlayerProjection, Sport, StatBreakdown } from '../../lib/types';
import { useSport } from '../_layout';

type Role = 'batter' | 'pitcher';

function StatItem({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.statItem}>
      <Text style={S.label}>{label}</Text>
      <Text style={S.value}>{value}</Text>
    </View>
  );
}

// ── Big projected stat tile ───────────────────────────────────────────────────
function ProjectedTile({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.projTile}>
      <Text style={styles.projValue}>{value}</Text>
      <Text style={styles.projLabel}>{label}</Text>
    </View>
  );
}

// ── Per-stat breakdown row ────────────────────────────────────────────────────
function BreakdownRow({ label, bd }: { label: string; bd: StatBreakdown }) {
  const defColor = bd.def_factor > 1.05 ? C.win : bd.def_factor < 0.95 ? C.loss : C.sub;
  const defLabel = bd.def_factor > 1.05 ? `+${((bd.def_factor - 1) * 100).toFixed(0)}%` :
    bd.def_factor < 0.95 ? `${((bd.def_factor - 1) * 100).toFixed(0)}%` : 'avg';

  return (
    <View style={styles.bdRow}>
      <Text style={styles.bdStatLabel}>{label}</Text>
      <Text style={styles.bdCell}>{bd.season_avg}</Text>
      <Text style={[styles.bdCell, { color: bd.h2h_avg_shrunk !== null ? C.primary : C.sub }]}>
        {bd.h2h_avg_shrunk !== null
          ? `${bd.h2h_avg_shrunk}${bd.h2h_games > 0 ? ` (${bd.h2h_games}g)` : ''}`
          : '—'}
      </Text>
      <Text style={styles.bdCell}>{bd.recent_avg_5g}</Text>
      <Text style={[styles.bdCell, { color: defColor }]}>{defLabel}</Text>
      <Text style={[styles.bdCell, styles.bdProjected]}>{bd.projected}</Text>
    </View>
  );
}

// ── Confidence badge ──────────────────────────────────────────────────────────
function ConfidenceBadge({ level }: { level: 'high' | 'medium' | 'low' }) {
  const color = level === 'high' ? C.win : level === 'medium' ? '#f0a500' : C.loss;
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{level.toUpperCase()}</Text>
    </View>
  );
}

// ── Streak badge ──────────────────────────────────────────────────────────────
function StreakBadge({ context }: { context: 'hot' | 'cold' | 'normal' }) {
  if (context === 'normal') return null;
  const label = context === 'hot' ? '🔥 HOT' : '❄️ COLD';
  const color = context === 'hot' ? '#ff6b35' : '#5b9cf7';
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

// ── Player Projection card ────────────────────────────────────────────────────
function ProjectionCard({ proj }: { proj: PlayerProjection }) {
  const [showLog, setShowLog] = useState(false);
  const stats = ['points', 'assists', 'rebounds', 'steals'] as const;
  const statLabels = { points: 'PTS', assists: 'AST', rebounds: 'REB', steals: 'STL' };

  const minTrend = proj.minutes_trend;
  const minColor = minTrend > 1.05 ? C.win : minTrend < 0.95 ? C.loss : C.sub;
  const minTrendLabel = minTrend > 1.05
    ? `↑ +${((minTrend - 1) * 100).toFixed(0)}% vs season`
    : minTrend < 0.95
    ? `↓ ${((minTrend - 1) * 100).toFixed(0)}% vs season`
    : 'avg vs season';

  return (
    <View style={styles.projCard}>
      {/* Header row */}
      <View style={styles.projHeader}>
        <Text style={styles.projVsLabel}>vs {proj.opponent}</Text>
        <View style={styles.badgeRow}>
          <ConfidenceBadge level={proj.confidence} />
          <StreakBadge context={proj.streak_context} />
        </View>
      </View>

      {/* Injury warning */}
      {proj.injury_status && proj.injury_status !== 'probable' && (
        <View style={styles.injuryBanner}>
          <Text style={styles.injuryText}>
            ⚠ {proj.injury_status.toUpperCase()}
            {proj.injury_detail ? `  ·  ${proj.injury_detail}` : ''}
          </Text>
        </View>
      )}

      {/* Big projected stat tiles */}
      <View style={styles.projTileRow}>
        {stats.map((s) => (
          <ProjectedTile key={s} label={statLabels[s]} value={proj.projected[s]} />
        ))}
      </View>

      {/* Minutes context */}
      <Text style={[styles.minutesNote, { color: minColor }]}>
        {proj.recent_minutes} min (recent)  ·  {minTrendLabel}
      </Text>

      {/* Breakdown table */}
      <Text style={[S.section, { marginTop: 12 }]}>Breakdown</Text>
      <View style={styles.bdHeader}>
        <Text style={styles.bdStatLabel} />
        <Text style={styles.bdHeaderCell}>Season</Text>
        <Text style={styles.bdHeaderCell}>H2H</Text>
        <Text style={styles.bdHeaderCell}>Last 5</Text>
        <Text style={styles.bdHeaderCell}>Def</Text>
        <Text style={[styles.bdHeaderCell, { color: C.primary }]}>Proj</Text>
      </View>
      {stats.map((s) => (
        <BreakdownRow key={s} label={statLabels[s]} bd={proj.breakdown[s]} />
      ))}

      {/* H2H game log */}
      {proj.h2h_log.length > 0 && (
        <>
          <TouchableOpacity
            style={styles.logToggle}
            onPress={() => setShowLog((v) => !v)}
          >
            <Text style={styles.logToggleText}>
              {showLog ? '▲' : '▼'}  H2H Game Log ({proj.h2h_games} games)
            </Text>
          </TouchableOpacity>

          {showLog && (
            <>
              <View style={styles.logHeader}>
                {['Date', 'PTS', 'AST', 'REB', 'STL', 'MIN'].map((h) => (
                  <Text key={h} style={styles.logHeaderCell}>{h}</Text>
                ))}
              </View>
              {proj.h2h_log.map((row, i) => (
                <View key={i} style={styles.logRow}>
                  <Text style={styles.logCell} numberOfLines={1}>
                    {String(row.date ?? '').slice(5)}
                  </Text>
                  <Text style={styles.logCell}>{String(row.points ?? '–')}</Text>
                  <Text style={styles.logCell}>{String(row.assists ?? '–')}</Text>
                  <Text style={styles.logCell}>{String(row.rebounds ?? '–')}</Text>
                  <Text style={styles.logCell}>{String(row.steals ?? '–')}</Text>
                  <Text style={styles.logCell}>{String(row.minutes ?? '–')}</Text>
                </View>
              ))}
            </>
          )}
        </>
      )}

      {proj.h2h_games === 0 && (
        <Text style={styles.noH2H}>No H2H history — projection based on season & recent form only</Text>
      )}
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export default function PlayersScreen() {
  const { sport, setSport } = useSport();
  const [role, setRole] = useState<Role>('batter');
  const [search, setSearch] = useState('');
  const [allPlayers, setAllPlayers] = useState<string[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState('');
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [log, setLog] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingPlayers, setLoadingPlayers] = useState(false);

  // Projection state (NBA only)
  const [teams, setTeams] = useState<string[]>([]);
  const [opponent, setOpponent] = useState('');
  const [projection, setProjection] = useState<PlayerProjection | null>(null);
  const [loadingProj, setLoadingProj] = useState(false);
  const [projError, setProjError] = useState('');

  const loadPlayers = useCallback(async (s: Sport, r: Role, q: string) => {
    setLoadingPlayers(true);
    try {
      const names = await api.players(s, { name: q, role: s === 'MLB' ? r : '' });
      setAllPlayers(names);
    } catch {
      setAllPlayers([]);
    } finally {
      setLoadingPlayers(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => loadPlayers(sport, role, search), 300);
    return () => clearTimeout(t);
  }, [sport, role, search, loadPlayers]);

  const loadStats = useCallback(async (player: string) => {
    if (!player) return;
    setLoading(true);
    setStats(null);
    setLog([]);
    setProjection(null);
    setOpponent('');
    setProjError('');
    try {
      const [s, l] = await Promise.all([
        api.playerStats(sport, player, 15, role),
        api.playerLog(sport, player, 15, role),
      ]);
      setStats(s as unknown as Record<string, unknown>);
      setLog(l);
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [sport, role]);

  // Load NBA teams list once when a player is selected
  useEffect(() => {
    if (selectedPlayer && sport === 'NBA' && teams.length === 0) {
      api.teams('NBA').then(setTeams).catch(() => {});
    }
  }, [selectedPlayer, sport, teams.length]);

  useEffect(() => { if (selectedPlayer) loadStats(selectedPlayer); }, [selectedPlayer, loadStats]);

  // Fetch projection whenever opponent changes
  useEffect(() => {
    if (!opponent || sport !== 'NBA') return;
    setLoadingProj(true);
    setProjection(null);
    setProjError('');
    api.playerProjected(selectedPlayer, opponent)
      .then(setProjection)
      .catch((e) => setProjError(e.message ?? 'Failed to load projection'))
      .finally(() => setLoadingProj(false));
  }, [opponent, selectedPlayer, sport]);

  const isMLB = sport === 'MLB';

  const renderStats = () => {
    if (!stats || Object.keys(stats).length === 0) return null;
    const skip = new Set(['player', 'games', 'opponent']);
    const entries = Object.entries(stats).filter(([k]) => !skip.has(k));
    return (
      <View style={styles.statsGrid}>
        {entries.map(([k, v]) => (
          <StatItem key={k} label={k} value={typeof v === 'number' ? String(v) : String(v ?? '–')} />
        ))}
      </View>
    );
  };

  const logColumns = isMLB
    ? (role === 'pitcher'
        ? ['date', 'opponent', 'innings_pitched', 'earned_runs', 'strikeouts_pitched', 'walks_allowed']
        : ['date', 'opponent', 'at_bats', 'hits', 'home_runs', 'rbi'])
    : ['date', 'opponent', 'points', 'assists', 'rebounds'];

  const colLabels: Record<string, string> = {
    date: 'Date', opponent: 'Opp', innings_pitched: 'IP', earned_runs: 'ER',
    strikeouts_pitched: 'K', walks_allowed: 'BB', at_bats: 'AB', hits: 'H',
    home_runs: 'HR', rbi: 'RBI', points: 'PTS', assists: 'AST', rebounds: 'REB',
  };

  return (
    <SafeAreaView style={S.screen}>
      <FlatList
        data={(selectedPlayer ? log : allPlayers.slice(0, 50)) as unknown[]}
        keyExtractor={(item, i) =>
          selectedPlayer
            ? String((item as Record<string, unknown>)['date']) + i
            : String(item)
        }
        ListHeaderComponent={
          <View style={styles.header}>
            <Text style={S.title}>Players</Text>
            <SportSelector value={sport} onChange={(s) => { setSport(s); setSelectedPlayer(''); setSearch(''); setOpponent(''); setTeams([]); }} />

            {isMLB && (
              <View style={styles.roleRow}>
                {(['batter', 'pitcher'] as Role[]).map((r) => (
                  <TouchableOpacity
                    key={r}
                    style={[styles.roleBtn, role === r && styles.roleBtnActive]}
                    onPress={() => { setRole(r); setSelectedPlayer(''); }}
                  >
                    <Text style={[styles.roleText, role === r && { color: C.primary }]}>
                      {r === 'batter' ? '🏏 Batters' : '⚾ Pitchers'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {selectedPlayer ? (
              <>
                <TouchableOpacity style={styles.back} onPress={() => { setSelectedPlayer(''); setOpponent(''); setProjection(null); }}>
                  <Text style={{ color: C.primary }}>← Back to list</Text>
                </TouchableOpacity>
                <Text style={styles.playerName}>{selectedPlayer}</Text>

                {loading ? (
                  <ActivityIndicator color={C.primary} style={{ margin: 20 }} />
                ) : (
                  <>
                    <Text style={S.section}>Season Stats ({(stats?.games as number) ?? 0} games)</Text>
                    {renderStats()}

                    {/* ── Project vs Team (NBA only) ── */}
                    {!isMLB && (
                      <>
                        <Text style={[S.section, { marginTop: 20 }]}>Project vs Opponent</Text>
                        <TeamPicker
                          label="Select opponent team"
                          teams={teams}
                          value={opponent}
                          onChange={(t) => { setOpponent(t); setProjection(null); }}
                        />

                        {loadingProj && (
                          <ActivityIndicator color={C.primary} style={{ margin: 16 }} />
                        )}

                        {projError ? (
                          <Text style={styles.projError}>{projError}</Text>
                        ) : projection ? (
                          <ProjectionCard proj={projection} />
                        ) : null}
                      </>
                    )}

                    <Text style={[S.section, { marginTop: 20 }]}>Game Log</Text>
                    <View style={styles.logHeader}>
                      {logColumns.map((c) => (
                        <Text key={c} style={styles.logHeaderCell}>{colLabels[c] ?? c}</Text>
                      ))}
                    </View>
                  </>
                )}
              </>
            ) : (
              <>
                <TextInput
                  style={styles.search}
                  placeholder="Search player..."
                  placeholderTextColor={C.sub}
                  value={search}
                  onChangeText={setSearch}
                />
                {loadingPlayers && <ActivityIndicator color={C.primary} size="small" style={{ marginBottom: 8 }} />}
              </>
            )}
          </View>
        }
        renderItem={({ item }) => {
          if (selectedPlayer) {
            const row = item as Record<string, unknown>;
            return (
              <View style={styles.logRow}>
                {logColumns.map((c) => (
                  <Text key={c} style={styles.logCell} numberOfLines={1}>
                    {c === 'opponent' ? String(row[c] ?? '').split(' ').pop() : String(row[c] ?? '–')}
                  </Text>
                ))}
              </View>
            );
          }
          const playerName = item as unknown as string;
          return (
            <TouchableOpacity style={styles.playerRow} onPress={() => setSelectedPlayer(playerName)}>
              <Text style={styles.playerRowText}>{playerName}</Text>
              <Text style={{ color: C.sub }}>›</Text>
            </TouchableOpacity>
          );
        }}
        contentContainerStyle={{ paddingBottom: 40 }}
        ListEmptyComponent={
          !loadingPlayers ? <Text style={styles.empty}>No players found.</Text> : null
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { padding: 16 },
  roleRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  roleBtn: {
    flex: 1, paddingVertical: 8, borderRadius: 8,
    borderWidth: 1, borderColor: C.border, alignItems: 'center',
  },
  roleBtnActive: { borderColor: C.primary, backgroundColor: C.primary + '15' },
  roleText: { color: C.sub, fontSize: 13, fontWeight: '600' },
  back: { marginBottom: 8 },
  playerName: { color: C.text, fontSize: 18, fontWeight: '700', marginBottom: 4 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  statItem: {
    backgroundColor: C.card, borderRadius: 8, padding: 10,
    minWidth: '28%', flex: 1,
  },
  search: {
    backgroundColor: C.card, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 9,
    color: C.text, fontSize: 15,
    borderWidth: 1, borderColor: C.border, marginBottom: 8,
  },
  playerRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border,
  },
  playerRowText: { color: C.text, fontSize: 15 },

  // ── Projection card ────────────────────────────────────────────────────
  projCard: {
    backgroundColor: C.card, borderRadius: 10,
    padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  projHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 8,
  },
  projVsLabel: { color: C.text, fontSize: 15, fontWeight: '700' },
  badgeRow: { flexDirection: 'row', gap: 6 },
  badge: {
    borderWidth: 1, borderRadius: 4,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  badgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },

  injuryBanner: {
    backgroundColor: C.loss + '22', borderRadius: 6,
    paddingHorizontal: 10, paddingVertical: 6, marginBottom: 10,
    borderLeftWidth: 3, borderLeftColor: C.loss,
  },
  injuryText: { color: C.loss, fontSize: 12, fontWeight: '600' },

  projTileRow: {
    flexDirection: 'row', gap: 8, marginBottom: 6,
  },
  projTile: {
    flex: 1, backgroundColor: C.bg, borderRadius: 8,
    paddingVertical: 12, alignItems: 'center',
    borderWidth: 1, borderColor: C.border,
  },
  projValue: { color: C.primary, fontSize: 22, fontWeight: '800' },
  projLabel: { color: C.sub, fontSize: 11, fontWeight: '600', marginTop: 2 },

  minutesNote: { fontSize: 11, textAlign: 'center', marginBottom: 4 },

  // ── Breakdown table ────────────────────────────────────────────────────
  bdHeader: {
    flexDirection: 'row', paddingVertical: 4,
    borderBottomWidth: 1, borderBottomColor: C.border, marginBottom: 2,
  },
  bdRow: {
    flexDirection: 'row', paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border,
  },
  bdStatLabel: { width: 36, color: C.sub, fontSize: 11, fontWeight: '700' },
  bdHeaderCell: { flex: 1, color: C.sub, fontSize: 10, textAlign: 'center' },
  bdCell: { flex: 1, color: C.text, fontSize: 12, textAlign: 'center' },
  bdSmall: { fontSize: 9, color: C.sub },
  bdProjected: { color: C.primary, fontWeight: '700' },

  // ── H2H log ────────────────────────────────────────────────────────────
  logToggle: { marginTop: 12, paddingVertical: 8, alignItems: 'center' },
  logToggleText: { color: C.primary, fontSize: 12, fontWeight: '600' },
  logHeader: {
    flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  logHeaderCell: { flex: 1, color: C.sub, fontSize: 11, textAlign: 'center' },
  logRow: {
    flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border,
  },
  logCell: { flex: 1, color: C.text, fontSize: 13, textAlign: 'center' },

  noH2H: { color: C.sub, fontSize: 11, textAlign: 'center', marginTop: 8, fontStyle: 'italic' },
  projError: { color: C.loss, fontSize: 13, textAlign: 'center', marginTop: 8 },

  empty: { color: C.sub, textAlign: 'center', marginTop: 40 },
});
