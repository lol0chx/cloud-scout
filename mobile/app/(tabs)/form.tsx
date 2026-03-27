import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import SportSelector from '../../components/SportSelector';
import TeamPicker from '../../components/TeamPicker';
import { api } from '../../lib/api';
import { C, S } from '../../lib/theme';
import type { FormGame, Sport, TeamForm } from '../../lib/types';
import { useSport } from '../_layout';

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.statCard}>
      <Text style={S.label}>{label}</Text>
      <Text style={[S.value, color ? { color } : {}]}>{value}</Text>
    </View>
  );
}

export default function FormScreen() {
  const { sport, setSport } = useSport();
  const [teams, setTeams] = useState<string[]>([]);
  const [team, setTeam] = useState('');
  const [form, setForm] = useState<TeamForm | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.teams(sport).then((t) => { setTeams(t); if (t.length) setTeam(t[0]); }).catch(() => {});
  }, [sport]);

  const load = useCallback(async () => {
    if (!team) return;
    setLoading(true);
    setError('');
    try {
      setForm(await api.teamForm(sport, team));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setForm(null);
    } finally {
      setLoading(false);
    }
  }, [sport, team]);

  useEffect(() => { load(); }, [load]);

  const netColor = form ? (form.net_rating >= 0 ? C.win : C.loss) : C.text;
  const streakColor = form?.streak_type === 'W' ? C.win : C.loss;
  const isMLB = sport === 'MLB';

  return (
    <SafeAreaView style={S.screen}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={C.primary} />}
      >
        <Text style={S.title}>Team Form</Text>
        <SportSelector value={sport} onChange={setSport} />
        <TeamPicker label="Team" teams={teams} value={team} onChange={setTeam} />

        {error ? (
          <Text style={styles.error}>{error}</Text>
        ) : loading && !form ? (
          <ActivityIndicator color={C.primary} style={{ marginTop: 40 }} />
        ) : form ? (
          <>
            <View style={styles.statsGrid}>
              <StatCard label="Games" value={String(form.games)} />
              <StatCard
                label="Streak"
                value={`${form.streak_type}${form.streak_count}`}
                color={streakColor}
              />
              <StatCard label={isMLB ? 'Avg Runs' : 'Avg Scored'} value={String(form.avg_scored)} />
              <StatCard label={isMLB ? 'Avg Allowed' : 'Avg Conceded'} value={String(form.avg_conceded)} />
              <StatCard
                label={isMLB ? 'Run Diff' : 'Net Rating'}
                value={`${form.net_rating >= 0 ? '+' : ''}${form.net_rating}`}
                color={netColor}
              />
            </View>

            <Text style={S.section}>Game Log</Text>
            {form.form_log.map((g: FormGame, i) => {
              const won = g.result === 'W';
              return (
                <View key={i} style={[styles.logRow, { borderLeftColor: won ? C.win : C.loss }]}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.logOpponent} numberOfLines={1}>
                      {g.location === 'Home' ? 'vs' : '@'} {g.opponent}
                    </Text>
                    <Text style={styles.logDate}>{g.date}</Text>
                  </View>
                  <Text style={[styles.logResult, { color: won ? C.win : C.loss }]}>{g.result}</Text>
                  <Text style={styles.logScore}>
                    {g.scored}–{g.conceded}
                  </Text>
                  <Text style={styles.logAvg}>{g.rolling_avg}</Text>
                </View>
              );
            })}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 40 },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  statCard: {
    backgroundColor: C.card,
    borderRadius: 10,
    padding: 12,
    minWidth: '30%',
    flex: 1,
  },
  error: { color: C.loss, textAlign: 'center', marginTop: 20 },
  logRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
    borderLeftWidth: 3,
    gap: 8,
  },
  logOpponent: { color: C.text, fontSize: 13, fontWeight: '500' },
  logDate: { color: C.sub, fontSize: 11, marginTop: 2 },
  logResult: { fontSize: 13, fontWeight: '700', width: 20 },
  logScore: { color: C.text, fontSize: 13, fontWeight: '600', width: 55, textAlign: 'center' },
  logAvg: { color: C.sub, fontSize: 12, width: 36, textAlign: 'right' },
});
