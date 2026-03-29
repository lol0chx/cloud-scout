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
import { api } from '../../lib/api';
import { C, S } from '../../lib/theme';
import type { Standing } from '../../lib/types';
import { useSport } from '../_layout';

export default function StandingsScreen() {
  const { sport, setSport } = useSport();
  const [standings, setStandings] = useState<Standing[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setStandings(await api.standings(sport));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [sport]);

  useEffect(() => { load(); }, [load]);

  const renderHeader = () => (
    <View style={[styles.row, styles.headerRow]}>
      <Text style={[styles.cell, styles.teamCell, { color: C.sub }]}>Team</Text>
      <Text style={[styles.cell, { color: C.sub }]}>W</Text>
      <Text style={[styles.cell, { color: C.sub }]}>L</Text>
      <Text style={[styles.cell, { color: C.sub }]}>Win%</Text>
      <Text style={[styles.cell, { color: C.sub }]}>Net</Text>
      <Text style={[styles.cell, { color: C.sub }]}>Str</Text>
    </View>
  );

  const renderItem = ({ item, index }: { item: Standing; index: number }) => {
    const net = item['Net Rtg'];
    const netColor = net > 0 ? C.win : net < 0 ? C.loss : C.text;
    const streakWin = item.Streak?.startsWith('W');

    return (
      <View style={[styles.row, index % 2 === 0 && styles.rowAlt]}>
        <View style={[styles.cell, styles.teamCell]}>
          <Text style={styles.rank}>{index + 1}</Text>
          <Text style={styles.teamName} numberOfLines={1}>{item.Team}</Text>
        </View>
        <Text style={styles.cell}>{item.W}</Text>
        <Text style={styles.cell}>{item.L}</Text>
        <Text style={styles.cell}>{item['Win%']}%</Text>
        <Text style={[styles.cell, { color: netColor, fontWeight: '700' }]}>
          {net > 0 ? '+' : ''}{net}
        </Text>
        <Text style={[styles.cell, { color: streakWin ? C.win : C.loss }]}>{item.Streak}</Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={S.screen}>
      <View style={styles.header}>
        <Text style={S.title}>Standings</Text>
        <SportSelector value={sport} onChange={setSport} />
      </View>

      {error ? (
        <Text style={styles.error}>{error}</Text>
      ) : (
        <FlatList
          data={standings}
          keyExtractor={(item) => item.Team}
          renderItem={renderItem}
          ListHeaderComponent={renderHeader}
          stickyHeaderIndices={[0]}
          contentContainerStyle={{ paddingBottom: 20 }}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={C.primary} />}
          ListEmptyComponent={
            loading ? (
              <ActivityIndicator color={C.primary} style={{ marginTop: 40 }} />
            ) : (
              <Text style={styles.empty}>No data yet.</Text>
            )
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, paddingTop: 16 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  rowAlt: { backgroundColor: C.card + '55' },
  headerRow: {
    backgroundColor: C.bg,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  cell: { width: 44, textAlign: 'center', color: C.text, fontSize: 13 },
  teamCell: {
    flex: 1,
    width: undefined,
    flexDirection: 'row',
    alignItems: 'center',
    textAlign: 'left',
  },
  rank: { color: C.sub, fontSize: 12, width: 22 },
  teamName: { color: C.text, fontSize: 13, flex: 1 },
  error: { color: C.loss, textAlign: 'center', margin: 20 },
  empty: { color: C.sub, textAlign: 'center', marginTop: 40 },
});
