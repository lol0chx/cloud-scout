import React, { useState } from 'react';
import {
  FlatList,
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { C } from '../lib/theme';

interface Props {
  label?: string;
  teams: string[];
  value: string;
  onChange: (t: string) => void;
}

export default function TeamPicker({ label, teams, value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const filtered = search
    ? teams.filter((t) => t.toLowerCase().includes(search.toLowerCase()))
    : teams;

  return (
    <>
      {label && <Text style={styles.label}>{label}</Text>}
      <TouchableOpacity style={styles.trigger} onPress={() => setOpen(true)}>
        <Text style={styles.triggerText} numberOfLines={1}>
          {value || 'Select team'}
        </Text>
        <Text style={styles.arrow}>▾</Text>
      </TouchableOpacity>

      <Modal visible={open} animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modal}>
          <View style={styles.header}>
            <Text style={styles.headerTitle}>Select Team</Text>
            <TouchableOpacity onPress={() => { setOpen(false); setSearch(''); }}>
              <Text style={styles.close}>Done</Text>
            </TouchableOpacity>
          </View>
          <TextInput
            style={styles.search}
            placeholder="Search..."
            placeholderTextColor={C.sub}
            value={search}
            onChangeText={setSearch}
            autoFocus
          />
          <FlatList
            data={filtered}
            keyExtractor={(item) => item}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={[styles.item, item === value && styles.itemActive]}
                onPress={() => {
                  onChange(item);
                  setOpen(false);
                  setSearch('');
                }}
              >
                <Text style={[styles.itemText, item === value && { color: C.primary }]}>
                  {item}
                </Text>
                {item === value && <Text style={{ color: C.primary }}>✓</Text>}
              </TouchableOpacity>
            )}
          />
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  label: { color: C.sub, fontSize: 12, marginBottom: 4 },
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  triggerText: { flex: 1, color: C.text, fontSize: 15 },
  arrow: { color: C.sub, fontSize: 12 },
  modal: { flex: 1, backgroundColor: C.bg },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  headerTitle: { color: C.text, fontSize: 17, fontWeight: '600' },
  close: { color: C.primary, fontSize: 16 },
  search: {
    margin: 12,
    backgroundColor: C.card,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    color: C.text,
    fontSize: 15,
    borderWidth: 1,
    borderColor: C.border,
  },
  item: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  itemActive: { backgroundColor: C.primary + '11' },
  itemText: { color: C.text, fontSize: 15 },
});
