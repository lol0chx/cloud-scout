import React, { useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
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
import { useSport } from '../_layout';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function AIScreen() {
  const { sport, setSport } = useSport();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<FlatList>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');

    const userMsg: Message = { role: 'user', content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setLoading(true);

    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);

    try {
      const history = updated.slice(-10).map((m) => ({ role: m.role, content: m.content }));
      const { response } = await api.aiChat(sport, text, history);
      setMessages((prev) => [...prev, { role: 'assistant', content: response }]);
    } catch (e: unknown) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: e instanceof Error ? `Error: ${e.message}` : 'Something went wrong.' },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
        <Text style={[styles.bubbleText, isUser && styles.userText]}>{item.content}</Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={S.screen}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        <View style={styles.header}>
          <Text style={S.title}>AI Scout</Text>
          <SportSelector value={sport} onChange={(s) => { setSport(s); setMessages([]); }} />
        </View>

        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(_, i) => String(i)}
          renderItem={renderMessage}
          contentContainerStyle={styles.list}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>🤖</Text>
              <Text style={styles.emptyTitle}>AI Scout</Text>
              <Text style={styles.emptySub}>
                Ask about {sport} teams, players, matchups, or standings.
              </Text>
              {['Who leads in scoring?', 'Best record in the league?', 'Predict the next game'].map((q) => (
                <TouchableOpacity key={q} style={styles.suggestion} onPress={() => setInput(q)}>
                  <Text style={styles.suggestionText}>{q}</Text>
                </TouchableOpacity>
              ))}
            </View>
          }
        />

        {loading && (
          <View style={styles.typing}>
            <ActivityIndicator size="small" color={C.primary} />
            <Text style={styles.typingText}>Thinking...</Text>
          </View>
        )}

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder={`Ask about ${sport}...`}
            placeholderTextColor={C.sub}
            value={input}
            onChangeText={setInput}
            onSubmitEditing={send}
            returnKeyType="send"
            multiline
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || loading) && styles.sendBtnDisabled]}
            onPress={send}
            disabled={!input.trim() || loading}
          >
            <Text style={styles.sendIcon}>↑</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, paddingTop: 16 },
  list: { paddingHorizontal: 16, paddingBottom: 8, flexGrow: 1 },
  bubble: {
    maxWidth: '82%', borderRadius: 16, padding: 12, marginBottom: 8,
  },
  userBubble: { backgroundColor: C.primary, alignSelf: 'flex-end', borderBottomRightRadius: 4 },
  aiBubble: { backgroundColor: C.card, alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  bubbleText: { color: C.text, fontSize: 15, lineHeight: 21 },
  userText: { color: '#fff' },
  emptyContainer: { flex: 1, alignItems: 'center', paddingTop: 40, paddingHorizontal: 24 },
  emptyIcon: { fontSize: 44, marginBottom: 12 },
  emptyTitle: { color: C.text, fontSize: 18, fontWeight: '700', marginBottom: 6 },
  emptySub: { color: C.sub, fontSize: 14, textAlign: 'center', marginBottom: 24, lineHeight: 20 },
  suggestion: {
    borderWidth: 1, borderColor: C.border, borderRadius: 20,
    paddingHorizontal: 14, paddingVertical: 8, marginBottom: 8,
  },
  suggestionText: { color: C.sub, fontSize: 13 },
  typing: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 6, gap: 8 },
  typingText: { color: C.sub, fontSize: 13 },
  inputRow: {
    flexDirection: 'row', alignItems: 'flex-end', gap: 8,
    paddingHorizontal: 12, paddingVertical: 10,
    borderTopWidth: 1, borderTopColor: C.border,
  },
  input: {
    flex: 1, backgroundColor: C.card, borderRadius: 20,
    paddingHorizontal: 14, paddingVertical: 10,
    color: C.text, fontSize: 15, maxHeight: 100,
    borderWidth: 1, borderColor: C.border,
  },
  sendBtn: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { backgroundColor: C.border },
  sendIcon: { color: '#fff', fontSize: 18, fontWeight: '700' },
});
