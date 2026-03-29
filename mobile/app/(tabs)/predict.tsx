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
import type { Prediction, Sport } from '../../lib/types';
import { useSport } from '../_layout';

export default function PredictScreen() {
  const { sport, setSport } = useSport();
  const [teams, setTeams] = useState<string[]>([]);
  const [teamA, setTeamA] = useState('');
  const [teamB, setTeamB] = useState('');
  const [result, setResult] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.teams(sport).then((t) => {
      setTeams(t);
      setTeamA(t[0] ?? '');
      setTeamB(t[1] ?? '');
      setResult(null);
    }).catch(() => {});
  }, [sport]);

  const load = useCallback(async () => {
    if (!teamA || !teamB || teamA === teamB) return;
    setLoading(true);
    setError('');
    try {
      setResult(await api.prediction(sport, teamA, teamB));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [sport, teamA, teamB]);

  useEffect(() => { load(); }, [load]);

  const isMLB = sport === 'MLB';

  return (
    <SafeAreaView style={S.screen}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={C.primary} />}
      >
        <Text style={S.title}>Predictions</Text>
        <SportSelector value={sport} onChange={(s: Sport) => { setSport(s); setResult(null); }} />

        <View style={styles.pickers}>
          <View style={{ flex: 1 }}>
            <TeamPicker label="Team A" teams={teams} value={teamA} onChange={setTeamA} />
          </View>
          <Text style={styles.vs}>vs</Text>
          <View style={{ flex: 1 }}>
            <TeamPicker label="Team B" teams={teams} value={teamB} onChange={setTeamB} />
          </View>
        </View>

        {teamA === teamB && teamA && (
          <Text style={styles.warn}>Select two different teams.</Text>
        )}

        {error ? (
          <Text style={styles.error}>{error}</Text>
        ) : loading && !result ? (
          <ActivityIndicator color={C.primary} style={{ marginTop: 40 }} />
        ) : result ? (
          <>
            <Text style={S.section}>Win Probability</Text>
            <View style={styles.probRow}>
              <View style={[styles.probCard, { backgroundColor: result.prob_a >= result.prob_b ? C.win : C.loss }]}>
                <Text style={styles.probPct}>{result.prob_a}%</Text>
                <Text style={styles.probTeam} numberOfLines={2}>{result.team_a}</Text>
              </View>
              <View style={[styles.probCard, { backgroundColor: result.prob_b > result.prob_a ? C.win : C.loss }]}>
                <Text style={styles.probPct}>{result.prob_b}%</Text>
                <Text style={styles.probTeam} numberOfLines={2}>{result.team_b}</Text>
              </View>
            </View>

            <Text style={S.section}>{isMLB ? 'Run Line' : 'Spread'}</Text>
            <View style={S.card}>
              {result.margin > 0 ? (
                <Text style={styles.spread}>
                  <Text style={{ color: C.primary }}>{result.team_a}</Text>
                  {' favored by '}
                  <Text style={{ color: C.text, fontWeight: '700' }}>{Math.abs(result.margin)} {isMLB ? 'runs' : 'pts'}</Text>
                </Text>
              ) : result.margin < 0 ? (
                <Text style={styles.spread}>
                  <Text style={{ color: C.primary }}>{result.team_b}</Text>
                  {' favored by '}
                  <Text style={{ color: C.text, fontWeight: '700' }}>{Math.abs(result.margin)} {isMLB ? 'runs' : 'pts'}</Text>
                </Text>
              ) : (
                <Text style={styles.spread}>Pick 'em</Text>
              )}
            </View>

            <Text style={S.section}>Context</Text>
            <View style={styles.contextRow}>
              {[
                { team: result.team_a, rec: result.team_a_record, streak: result.team_a_streak },
                { team: result.team_b, rec: result.team_b_record, streak: result.team_b_streak },
              ].map(({ team, rec, streak }) => (
                <View key={team} style={[S.card, { flex: 1 }]}>
                  <Text style={styles.contextTeam} numberOfLines={2}>{team}</Text>
                  <Text style={styles.contextStat}>{rec.wins}W – {rec.losses}L</Text>
                  <Text style={styles.contextStat}>{rec.win_pct}% win</Text>
                  <Text style={[styles.contextStat, { color: streak.type === 'W' ? C.win : C.loss }]}>
                    {streak.type}{streak.count} streak
                  </Text>
                </View>
              ))}
            </View>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 40 },
  pickers: { flexDirection: 'row', alignItems: 'flex-end', gap: 8 },
  vs: { color: C.sub, fontSize: 14, marginBottom: 20, paddingHorizontal: 4 },
  probRow: { flexDirection: 'row', gap: 10, marginBottom: 4 },
  probCard: {
    flex: 1, borderRadius: 12, padding: 16, alignItems: 'center',
  },
  probPct: { color: '#fff', fontSize: 32, fontWeight: '800' },
  probTeam: { color: '#fff', fontSize: 12, marginTop: 4, textAlign: 'center', opacity: 0.9 },
  spread: { color: C.sub, fontSize: 15 },
  contextRow: { flexDirection: 'row', gap: 10 },
  contextTeam: { color: C.text, fontSize: 13, fontWeight: '600', marginBottom: 6 },
  contextStat: { color: C.sub, fontSize: 12, marginBottom: 2 },
  warn: { color: C.mlb, textAlign: 'center', marginBottom: 10 },
  error: { color: C.loss, textAlign: 'center', marginTop: 20 },
});
