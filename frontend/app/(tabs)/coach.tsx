import { useEffect, useRef, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, TextInput,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { api } from '@/src/services/api';
import { track } from '@/src/services/analytics';

const SESSION_ID = 'maya-default-session';

const SUGGESTIONS = [
  'Analyze my Q3 growth',
  'Where am I leaving money on the table?',
  'Draft a launch plan for Ship It v2',
  'Critique my latest YouTube hook',
];

type Msg = { id: string; role: 'user' | 'assistant'; text: string };

export default function Coach() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const scrollToEnd = () => requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));

  const loadHistory = useCallback(async () => {
    try {
      const r = await api.chatHistory(SESSION_ID);
      const mapped: Msg[] = r.messages.map((m: any) => ({ id: m.id, role: m.role, text: m.text }));
      setMessages(mapped);
      scrollToEnd();
    } catch (e) { console.warn(e); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const send = async (text: string) => {
    if (!text.trim() || streaming) return;
    const userMsg: Msg = { id: `u-${Date.now()}`, role: 'user', text };
    const aiMsg: Msg = { id: `a-${Date.now()}`, role: 'assistant', text: '' };
    setMessages(prev => [...prev, userMsg, aiMsg]);
    setInput('');
    setStreaming(true);
    scrollToEnd();

    track('ai_chat_message_sent', { len: text.length });
    const t0 = Date.now();
    let firstToken = 0;

    try {
      const resp = await fetch(api.chatUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify({ session_id: SESSION_ID, message: text }),
      });

      // Backend can return non-200 (402 quota / 413 too long / 429 burst)
      if (!resp.ok) {
        const msg = resp.status === 402 ? 'Free tier limit — upgrade for unlimited AI coach.'
                  : resp.status === 413 ? 'Message too long. Please shorten.'
                  : resp.status === 429 ? 'Slow down — try again in a moment.'
                  : 'AI service unavailable.';
        setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, text: `⚠ ${msg}` } : m));
        track('ai_chat_stream_error', { code: resp.status });
        if (resp.status === 402) track('quota_hit', { kind: 'chat' });
        return;
      }

      if (!resp.body) {
        // No streaming support — fall back to plain read
        const t = await resp.text();
        const parsed = t.split('\n').filter(l => l.startsWith('data:')).map(l => {
          try { return JSON.parse(l.slice(5).trim()); } catch { return null; }
        }).filter(Boolean);
        let acc = '';
        parsed.forEach((p: any) => { if (p.delta) acc += p.delta; });
        setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, text: acc } : m));
      } else {
        const reader = (resp.body as any).getReader();
        const decoder = new TextDecoder();
        let buf = '';
        let acc = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split('\n\n');
          buf = lines.pop() ?? '';
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:')) continue;
            try {
              const evt = JSON.parse(trimmed.slice(5).trim());
              if (evt.delta) {
                if (!firstToken) {
                  firstToken = Date.now();
                  track('ai_chat_stream_started', { ttft_ms: firstToken - t0 });
                }
                acc += evt.delta;
                setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, text: acc } : m));
                scrollToEnd();
              }
              if (evt.error) {
                setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, text: `⚠ ${evt.error}` } : m));
                track('ai_chat_stream_error', { code: 'stream_error' });
              }
            } catch {}
          }
        }
        track('ai_chat_stream_completed', { total_ms: Date.now() - t0, chars: acc.length });
      }
    } catch {
      setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, text: '⚠ Network error. Try again.' } : m));
      track('ai_chat_stream_error', { code: 'network' });
    } finally {
      setStreaming(false);
      scrollToEnd();
    }
  };

  const reset = async () => {
    await api.chatReset(SESSION_ID);
    setMessages([]);
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
    >
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <View style={styles.avatar}>
            <Ionicons name="flash" size={18} color={colors.brand} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>CreatorOS Coach</Text>
            <View style={styles.statusRow}>
              <View style={styles.statusDot} />
              <Text style={styles.statusText}>Claude Sonnet 4.5 · online</Text>
            </View>
          </View>
          <Pressable onPress={reset} style={styles.resetBtn} testID="chat-reset-btn">
            <Ionicons name="refresh" size={18} color={colors.onSurfaceSecondary} />
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView
        ref={scrollRef}
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        onContentSizeChange={scrollToEnd}
      >
        {messages.length === 0 && (
          <View style={styles.empty} testID="chat-empty">
            <View style={styles.bigAvatar}>
              <Ionicons name="flash" size={32} color={colors.brand} />
            </View>
            <Text style={styles.emptyTitle}>How can I help you grow?</Text>
            <Text style={styles.emptySub}>
              I see everything in your business — pick a thread or ask anything.
            </Text>
            <View style={styles.suggestions}>
              {SUGGESTIONS.map(s => (
                <Pressable key={s} onPress={() => send(s)} style={styles.suggestChip} testID={`suggest-${s.slice(0, 8)}`}>
                  <Text style={styles.suggestText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        )}

        {messages.map(m => (
          <View
            key={m.id}
            style={[styles.bubbleWrap, m.role === 'user' ? styles.bubbleWrapUser : styles.bubbleWrapAi]}
          >
            <View style={[styles.bubble, m.role === 'user' ? styles.bubbleUser : styles.bubbleAi]} testID={`msg-${m.role}`}>
              <Text style={[styles.bubbleText, m.role === 'user' ? styles.bubbleTextUser : styles.bubbleTextAi]}>
                {m.text || (streaming && m.role === 'assistant' ? '…' : '')}
              </Text>
            </View>
          </View>
        ))}
        {streaming && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.text && (
          <View style={[styles.bubbleWrap, styles.bubbleWrapAi]}>
            <View style={[styles.bubble, styles.bubbleAi, { flexDirection: 'row', gap: 6 }]}>
              <ActivityIndicator size="small" color={colors.brand} />
              <Text style={[styles.bubbleText, styles.bubbleTextAi]}>thinking…</Text>
            </View>
          </View>
        )}
      </ScrollView>

      <View style={styles.inputBar}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Ask the coach anything…"
          placeholderTextColor={colors.onSurfaceTertiary}
          style={styles.input}
          multiline
          maxLength={1000}
          editable={!streaming}
          testID="chat-input"
        />
        <Pressable
          onPress={() => send(input)}
          disabled={!input.trim() || streaming}
          style={[styles.sendBtn, (!input.trim() || streaming) && { opacity: 0.4 }]}
          testID="chat-send-btn"
        >
          <Ionicons name="arrow-up" size={20} color={colors.onBrandPrimary} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  avatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.brandTertiary, alignItems: 'center', justifyContent: 'center',
  },
  title: { color: colors.onSurface, fontSize: 16, fontWeight: '600', letterSpacing: -0.2 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 1 },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success },
  statusText: { color: colors.onSurfaceTertiary, fontSize: 11, fontWeight: '500' },
  resetBtn: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.surfaceSecondary,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },

  scroll: { paddingVertical: spacing.lg, paddingHorizontal: spacing.lg, paddingBottom: 120, gap: spacing.sm },

  empty: { alignItems: 'center', paddingVertical: spacing.xxl, gap: spacing.md },
  bigAvatar: {
    width: 64, height: 64, borderRadius: 32, backgroundColor: colors.brandTertiary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  emptyTitle: { color: colors.onSurface, fontSize: 20, fontWeight: '600', letterSpacing: -0.3 },
  emptySub: { color: colors.onSurfaceSecondary, fontSize: 13, textAlign: 'center', maxWidth: 260 },
  suggestions: { width: '100%', gap: spacing.sm, marginTop: spacing.md },
  suggestChip: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  suggestText: { color: colors.onSurface, fontSize: 14 },

  bubbleWrap: { width: '100%', flexDirection: 'row' },
  bubbleWrapUser: { justifyContent: 'flex-end' },
  bubbleWrapAi: { justifyContent: 'flex-start' },
  bubble: {
    maxWidth: '85%', paddingHorizontal: spacing.md, paddingVertical: spacing.md,
    borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth,
  },
  bubbleUser: { backgroundColor: colors.brandTertiary, borderColor: 'rgba(227,167,47,0.3)' },
  bubbleAi: { backgroundColor: colors.surfaceSecondary, borderColor: colors.border },
  bubbleText: { fontSize: 14, lineHeight: 21 },
  bubbleTextUser: { color: colors.brandSecondary },
  bubbleTextAi: { color: colors.onSurface },

  inputBar: {
    flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm,
    paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.divider,
    backgroundColor: colors.surface,
    marginBottom: 84, // sit above floating tab bar
  },
  input: {
    flex: 1, color: colors.onSurface, fontSize: 14,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 10,
    minHeight: 44, maxHeight: 120,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  sendBtn: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: colors.brand,
    alignItems: 'center', justifyContent: 'center',
  },
});
