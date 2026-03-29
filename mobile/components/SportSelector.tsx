import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { C } from '../lib/theme';
import type { Sport } from '../lib/types';

interface Props {
  value: Sport;
  onChange: (s: Sport) => void;
}

export default function SportSelector({ value, onChange }: Props) {
  return (
    <View style={styles.container}>
      {(['NBA', 'MLB'] as Sport[]).map((s) => {
        const active = value === s;
        const color = s === 'NBA' ? C.nba : C.mlb;
        return (
          <TouchableOpacity
            key={s}
            style={[styles.btn, active && { backgroundColor: color + '22', borderColor: color }]}
            onPress={() => onChange(s)}
          >
            <Text style={[styles.label, { color: active ? color : C.sub }]}>
              {s === 'NBA' ? '🏀 NBA' : '⚾ MLB'}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  btn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
  },
});
