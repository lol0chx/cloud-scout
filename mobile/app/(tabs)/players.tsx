import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import SportSelector from '../../components/SportSelector';
import { api } from '../../lib/api';
import { C, S } from '../../lib/theme';
import type { Sport } from '../../lib/types';
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

export default function PlayersScreen() {
  const { sport, setSport } = useSport();
  const [role, setRole] = useState<Role>('batter');
  const [search, setSearch] = useState('');
  const [allPlayers, setAllPlayers] = useState<string[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState('');
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [log, setLog] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingPlayers, setLoadingPlayers] = useState(false);

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
    try {
      const [s, l] = await Promise.all([
        api.playerStats(sport, player, 15, role),
        api.playerLog(sport, player, 15, role),
      ]);
      setStats(s as Record<string, unknown>);
      setLog(l);
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [sport, role]);

  useEffect(() => { if (selectedPlayer) loadStats(selectedPlayer); }, [selectedPlayer, loadStats]);

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
        data={selectedPlayer ? log : allPlayers.slice(0, 50)}
        keyExtractor={(item, i) =>
          selectedPlayer
            ? String((item as Record<string, unknown>)['date']) + i
            : String(item)
        }
        ListHeaderComponent={
          <View style={styles.header}>
            <Text style={S.title}>Players</Text>
            <SportSelector value={sport} onChange={(s) => { setSport(s); setSelectedPlayer(''); setSearch(''); }} />

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
                <TouchableOpacity style={styles.back} onPress={() => setSelectedPlayer('')}>
                  <Text style={{ color: C.primary }}>← Back to list</Text>
                </TouchableOpacity>
                <Text style={styles.playerName}>{selectedPlayer}</Text>
                {loading ? (
                  <ActivityIndicator color={C.primary} style={{ margin: 20 }} />
                ) : (
                  <>
                    <Text style={S.section}>Season Stats ({stats?.games ?? 0} games)</Text>
                    {renderStats()}
                    <Text style={S.section}>Game Log</Text>
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
          return (
            <TouchableOpacity style={styles.playerRow} onPress={() => setSelectedPlayer(item as string)}>
              <Text style={styles.playerRowText}>{item as string}</Text>
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
  empty: { color: C.sub, textAlign: 'center', marginTop: 40 },
});
