import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import SportSelector from '../../components/SportSelector';
import TeamPicker from '../../components/TeamPicker';
import { api } from '../../lib/api';
import { C, S } from '../../lib/theme';
import type { Game, Sport } from '../../lib/types';
import { useSport } from '../_layout';

export default function GamesScreen() {
  const { sport, setSport } = useSport();
  const [teams, setTeams] = useState<string[]>([]);
  const [team, setTeam] = useState('');
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadTeams = useCallback(async (s: Sport) => {
    try {
      const t = await api.teams(s);
      setTeams(t);
      setTeam('');
    } catch {
      setTeams([]);
    }
  }, []);

  const loadGames = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const g = await api.games(sport, team);
      setGames(g);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [sport, team]);

  useEffect(() => { loadTeams(sport); }, [sport]);
  useEffect(() => { loadGames(); }, [loadGames]);

  const renderGame = ({ item }: { item: Game }) => {
    const homeWon = item.home_score > item.away_score;
    const isTeamGame = team && (item.home_team === team || item.away_team === team);
    const isHome = item.home_team === team;
    const teamWon = isHome ? homeWon : !homeWon;
    const resultColor = isTeamGame ? (teamWon ? C.win : C.loss) : C.sub;

    return (
      <View style={[styles.gameCard, isTeamGame && { borderLeftWidth: 3, borderLeftColor: resultColor }]}>
        <Text style={styles.date}>{item.date}</Text>
        <View style={S.row}>
          <Text style={[styles.teamName, homeWon && { color: C.text }]} numberOfLines={1}>
            {item.home_team}
          </Text>
          <Text style={styles.score}>
            {item.home_score} – {item.away_score}
          </Text>
          <Text style={[styles.teamName, { textAlign: 'right' }, !homeWon && { color: C.text }]} numberOfLines={1}>
            {item.away_team}
          </Text>
        </View>
        {isTeamGame && (
          <Text style={[styles.result, { color: resultColor }]}>
            {teamWon ? 'W' : 'L'} · {isHome ? 'Home' : 'Away'}
          </Text>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={S.screen}>
      <View style={styles.header}>
        <Text style={S.title}>Game Results</Text>
        <SportSelector value={sport} onChange={(s) => { setSport(s); }} />
        <TeamPicker label="Filter by team" teams={['', ...teams]} value={team} onChange={setTeam} />
      </View>

      {error ? (
        <Text style={styles.error}>{error}</Text>
      ) : (
        <FlatList
          data={games}
          keyExtractor={(g) => String(g.id)}
          renderItem={renderGame}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 20 }}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={loadGames} tintColor={C.primary} />}
          ListEmptyComponent={
            loading ? (
              <ActivityIndicator color={C.primary} style={{ marginTop: 40 }} />
            ) : (
              <Text style={styles.empty}>No games. Scrape data from the web app first.</Text>
            )
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, paddingTop: 16 },
  gameCard: {
    backgroundColor: C.card,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  date: { color: C.sub, fontSize: 11, marginBottom: 6 },
  teamName: { flex: 1, color: C.sub, fontSize: 13 },
  score: {
    color: C.text,
    fontSize: 17,
    fontWeight: '700',
    marginHorizontal: 8,
    minWidth: 60,
    textAlign: 'center',
  },
  result: { fontSize: 11, fontWeight: '600', marginTop: 4 },
  error: { color: C.loss, textAlign: 'center', margin: 20 },
  empty: { color: C.sub, textAlign: 'center', marginTop: 40, paddingHorizontal: 20 },
});
