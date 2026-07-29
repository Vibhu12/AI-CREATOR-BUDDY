import { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator, Modal,
  TextInput, KeyboardAvoidingView, Platform, RefreshControl, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fmtCompact } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

type Goal = {
  id: string;
  title: string;
  kind: 'revenue' | 'followers' | 'subscribers' | 'launch' | 'content';
  target: number;
  current: number;
  deadline?: string;
};

const KIND_META: Record<string, { label: string; icon: any; color: string }> = {
  revenue:     { label: 'Revenue',     icon: 'cash',           color: '#45C97A' },
  followers:   { label: 'Followers',   icon: 'people',         color: '#E1306C' },
  subscribers: { label: 'Subscribers', icon: 'play-circle',    color: '#FF3D3D' },
  launch:      { label: 'Launch',      icon: 'rocket',         color: '#E3A72F' },
  content:     { label: 'Content',     icon: 'film',           color: '#635BFF' },
};

const KINDS: Goal['kind'][] = ['revenue', 'subscribers', 'followers', 'launch', 'content'];


function formatValue(kind: string, n: number) {
  if (kind === 'revenue') return `$${fmtCompact(n)}`;
  if (kind === 'launch') return `${Math.round(Math.min(1, n) * 100)}%`;
  return fmtCompact(n);
}


function daysLeft(deadline?: string): { text: string; urgent: boolean } | null {
  if (!deadline) return null;
  const now = new Date();
  const d = new Date(deadline);
  const days = Math.ceil((d.getTime() - now.getTime()) / 86_400_000);
  if (isNaN(days)) return null;
  if (days < 0) return { text: `${-days}d overdue`, urgent: true };
  if (days === 0) return { text: 'Today', urgent: true };
  if (days === 1) return { text: 'Tomorrow', urgent: true };
  if (days < 14) return { text: `${days}d left`, urgent: days < 7 };
  if (days < 60) return { text: `${Math.round(days / 7)}w left`, urgent: false };
  return { text: `${Math.round(days / 30)}mo left`, urgent: false };
}


export default function GoalsScreen() {
  const router = useRouter();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<Goal | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.goals();
      setGoals(r.items);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const total = goals.length;
  const done = goals.filter(g => g.current >= g.target).length;
  const avgPct = total
    ? Math.round(goals.reduce((s, g) => s + Math.min(100, (g.current / g.target) * 100), 0) / total)
    : 0;

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} testID="back-btn">
            <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>GOALS</Text>
            <Text style={styles.title}>Progress tracker</Text>
          </View>
          <Pressable
            style={styles.addBtn}
            onPress={() => setShowAdd(true)}
            testID="add-goal-btn"
          >
            <Ionicons name="add" size={20} color={colors.onBrandPrimary} />
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={styles.summaryCard}>
          <View style={styles.summaryCol}>
            <Text style={styles.summaryValue}>{total}</Text>
            <Text style={styles.summaryLabel}>Active</Text>
          </View>
          <View style={styles.vsep} />
          <View style={styles.summaryCol}>
            <Text style={styles.summaryValue}>{done}</Text>
            <Text style={styles.summaryLabel}>Completed</Text>
          </View>
          <View style={styles.vsep} />
          <View style={styles.summaryCol}>
            <Text style={[styles.summaryValue, { color: colors.brand }]}>{avgPct}%</Text>
            <Text style={styles.summaryLabel}>Avg progress</Text>
          </View>
        </View>

        {loading ? (
          <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.xl }} />
        ) : goals.length === 0 ? (
          <EmptyState onAdd={() => setShowAdd(true)} />
        ) : (
          <View style={{ marginTop: spacing.lg, gap: spacing.sm }}>
            {goals.map(g => (
              <GoalCard
                key={g.id}
                goal={g}
                onEdit={() => setEditing(g)}
                onDelete={async () => {
                  Alert.alert(
                    `Delete "${g.title}"?`,
                    'This cannot be undone.',
                    [
                      { text: 'Cancel', style: 'cancel' },
                      { text: 'Delete', style: 'destructive', onPress: async () => {
                        try { await api.deleteGoal(g.id); await load(); }
                        catch (e) { console.warn(e); }
                      } },
                    ],
                  );
                }}
              />
            ))}
          </View>
        )}
      </ScrollView>

      <GoalFormModal
        visible={showAdd || !!editing}
        goal={editing}
        onClose={() => { setShowAdd(false); setEditing(null); }}
        onSaved={async () => { setShowAdd(false); setEditing(null); await load(); }}
      />
    </View>
  );
}


function GoalCard({
  goal, onEdit, onDelete,
}: {
  goal: Goal;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const meta = KIND_META[goal.kind] ?? KIND_META.content;
  const pct = Math.min(100, Math.round((goal.current / goal.target) * 100));
  const complete = goal.current >= goal.target;
  const dl = daysLeft(goal.deadline);

  return (
    <Pressable
      onPress={onEdit}
      onLongPress={onDelete}
      style={[styles.gcard, complete && styles.gcardComplete]}
      testID={`goal-${goal.id}`}
    >
      <View style={styles.gcardTop}>
        <View style={[styles.gcardIcon, { backgroundColor: `${meta.color}22`, borderColor: `${meta.color}55` }]}>
          <Ionicons name={meta.icon} size={16} color={meta.color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.gcardTitle} numberOfLines={2}>{goal.title}</Text>
          <View style={styles.gcardMetaRow}>
            <Text style={styles.gcardMeta}>{meta.label}</Text>
            {dl && (
              <>
                <View style={styles.dot} />
                <Text style={[styles.gcardMeta, dl.urgent && { color: colors.warning, fontWeight: '700' }]}>
                  {dl.text}
                </Text>
              </>
            )}
          </View>
        </View>
        {complete && (
          <View style={styles.doneBadge}>
            <Ionicons name="checkmark" size={12} color={colors.success} />
          </View>
        )}
        <Text style={[styles.pct, complete && { color: colors.success }]}>{pct}%</Text>
      </View>

      <View style={styles.progressRow}>
        <Text style={styles.progressText}>
          {formatValue(goal.kind, goal.current)}
        </Text>
        <Text style={styles.progressTextMuted}>
          of {formatValue(goal.kind, goal.target)}
        </Text>
      </View>

      <View style={styles.barBg}>
        <View
          style={[
            styles.barFill,
            {
              width: `${pct}%`,
              backgroundColor: complete ? colors.success : meta.color,
            },
          ]}
        />
      </View>
    </Pressable>
  );
}


function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <View style={styles.emptyBlock}>
      <View style={styles.emptyIcon}>
        <Ionicons name="flag-outline" size={28} color={colors.brand} />
      </View>
      <Text style={styles.emptyTitle}>No goals yet</Text>
      <Text style={styles.emptySub}>
        Track revenue targets, subscriber milestones, and product launches all in one place.
      </Text>
      <Pressable style={styles.emptyBtn} onPress={onAdd} testID="empty-add-goal">
        <Ionicons name="add" size={14} color={colors.onBrandPrimary} />
        <Text style={styles.emptyBtnText}>Add your first goal</Text>
      </Pressable>
    </View>
  );
}


// ---------------------------------------------------------------------------
// Add / Edit modal
// ---------------------------------------------------------------------------
function GoalFormModal({
  visible, goal, onClose, onSaved,
}: {
  visible: boolean;
  goal: Goal | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState<Goal['kind']>('revenue');
  const [target, setTarget] = useState('');
  const [current, setCurrent] = useState('');
  const [deadline, setDeadline] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (goal) {
      setTitle(goal.title);
      setKind(goal.kind);
      setTarget(String(goal.target));
      setCurrent(String(goal.current));
      setDeadline(goal.deadline ?? '');
    } else {
      setTitle(''); setKind('revenue'); setTarget(''); setCurrent(''); setDeadline('');
    }
    setErr(null);
  }, [goal, visible]);

  const save = async () => {
    if (!title.trim()) { setErr('Title is required'); return; }
    const t = parseFloat(target);
    const c = parseFloat(current) || 0;
    if (isNaN(t) || t <= 0) { setErr('Target must be a positive number'); return; }
    if (c < 0) { setErr('Current cannot be negative'); return; }
    if (deadline && !/^\d{4}-\d{2}-\d{2}$/.test(deadline)) {
      setErr('Deadline must be YYYY-MM-DD');
      return;
    }
    setBusy(true); setErr(null);
    try {
      if (goal) {
        await api.updateGoal(goal.id, {
          title: title.trim(),
          target: t,
          current: c,
          deadline: deadline || undefined,
        });
      } else {
        await api.createGoal({
          title: title.trim(),
          kind,
          target: t,
          current: c,
          deadline: deadline || undefined,
        });
      }
      onSaved();
    } catch {
      setErr('Failed to save — try again');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <Pressable style={{ flex: 1 }} onPress={onClose} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ width: '100%' }}
        >
          <View style={styles.modalSheet}>
            <SafeAreaView edges={['bottom']}>
              <View style={styles.grabber} />
              <View style={styles.modalHead}>
                <View>
                  <Text style={styles.modalKicker}>{goal ? 'EDIT' : 'NEW'} GOAL</Text>
                  <Text style={styles.modalTitle}>{goal ? 'Update goal' : 'Set a target'}</Text>
                </View>
                <Pressable onPress={onClose} style={styles.closeBtn} testID="goal-close">
                  <Ionicons name="close" size={18} color={colors.onSurface} />
                </Pressable>
              </View>

              <ScrollView keyboardShouldPersistTaps="handled" style={styles.modalBody}>
                {!goal && (
                  <>
                    <Text style={styles.label}>TYPE</Text>
                    <ScrollView
                      horizontal
                      showsHorizontalScrollIndicator={false}
                      contentContainerStyle={styles.chipsRow}
                    >
                      {KINDS.map(k => {
                        const meta = KIND_META[k];
                        const active = kind === k;
                        return (
                          <Pressable
                            key={k}
                            onPress={() => setKind(k)}
                            style={[styles.chip, active && { backgroundColor: `${meta.color}22`, borderColor: meta.color }]}
                            testID={`kind-${k}`}
                          >
                            <Ionicons name={meta.icon} size={12} color={active ? meta.color : colors.onSurfaceSecondary} />
                            <Text style={[styles.chipText, active && { color: meta.color, fontWeight: '700' }]}>
                              {meta.label}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </ScrollView>
                  </>
                )}

                <Text style={styles.label}>TITLE</Text>
                <TextInput
                  value={title}
                  onChangeText={setTitle}
                  placeholder="e.g. 250K YouTube subs"
                  placeholderTextColor={colors.onSurfaceTertiary}
                  style={styles.input}
                  maxLength={120}
                  testID="goal-title"
                />

                <View style={styles.numRow}>
                  <View style={styles.numCol}>
                    <Text style={styles.label}>TARGET</Text>
                    <TextInput
                      value={target}
                      onChangeText={(t) => setTarget(t.replace(/[^0-9.]/g, ''))}
                      placeholder="250000"
                      placeholderTextColor={colors.onSurfaceTertiary}
                      keyboardType="decimal-pad"
                      style={styles.input}
                      testID="goal-target"
                    />
                  </View>
                  <View style={styles.numCol}>
                    <Text style={styles.label}>CURRENT</Text>
                    <TextInput
                      value={current}
                      onChangeText={(t) => setCurrent(t.replace(/[^0-9.]/g, ''))}
                      placeholder="0"
                      placeholderTextColor={colors.onSurfaceTertiary}
                      keyboardType="decimal-pad"
                      style={styles.input}
                      testID="goal-current"
                    />
                  </View>
                </View>

                <Text style={styles.label}>DEADLINE (YYYY-MM-DD, optional)</Text>
                <TextInput
                  value={deadline}
                  onChangeText={setDeadline}
                  placeholder="2026-12-31"
                  placeholderTextColor={colors.onSurfaceTertiary}
                  style={styles.input}
                  maxLength={10}
                  testID="goal-deadline"
                />

                {err && (
                  <View style={styles.errBox}>
                    <Ionicons name="alert-circle" size={13} color={colors.error} />
                    <Text style={styles.errText}>{err}</Text>
                  </View>
                )}

                <Pressable
                  onPress={save}
                  disabled={busy}
                  style={[styles.saveBtn, busy && { opacity: 0.6 }]}
                  testID="goal-save"
                >
                  {busy
                    ? <ActivityIndicator color={colors.onBrandPrimary} />
                    : <>
                        <Ionicons name={goal ? 'checkmark-circle' : 'add-circle'} size={16} color={colors.onBrandPrimary} />
                        <Text style={styles.saveBtnText}>{goal ? 'Save changes' : 'Create goal'}</Text>
                      </>
                  }
                </Pressable>

                {goal && (
                  <Text style={styles.hint}>Tip: long-press a goal on the list to delete it.</Text>
                )}
              </ScrollView>
            </SafeAreaView>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}


const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: 'row', alignItems: 'flex-end', gap: spacing.md,
    paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md,
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.surfaceSecondary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  kicker: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600' },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },
  addBtn: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.brand,
    alignItems: 'center', justifyContent: 'center',
  },

  summaryCard: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    paddingVertical: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  summaryCol: { flex: 1, alignItems: 'center' },
  summaryValue: { color: colors.onSurface, fontSize: 24, fontWeight: '700', letterSpacing: -1 },
  summaryLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, marginTop: 4, fontWeight: '600' },
  vsep: { width: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong, marginVertical: 4 },

  gcard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.sm,
  },
  gcardComplete: { borderColor: 'rgba(69,201,122,0.4)' },
  gcardTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  gcardIcon: {
    width: 36, height: 36, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  gcardTitle: { color: colors.onSurface, fontSize: 14, fontWeight: '600', letterSpacing: -0.2 },
  gcardMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  gcardMeta: { color: colors.onSurfaceTertiary, fontSize: 11, fontWeight: '500' },
  dot: { width: 2, height: 2, borderRadius: 1, backgroundColor: colors.onSurfaceTertiary },
  doneBadge: {
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: 'rgba(69,201,122,0.16)',
    alignItems: 'center', justifyContent: 'center',
  },
  pct: { color: colors.brand, fontSize: 14, fontWeight: '700', letterSpacing: -0.2 },

  progressRow: { flexDirection: 'row', gap: 4, alignItems: 'baseline' },
  progressText: { color: colors.onSurface, fontSize: 13, fontWeight: '600' },
  progressTextMuted: { color: colors.onSurfaceTertiary, fontSize: 11 },

  barBg: { height: 5, backgroundColor: colors.surfaceTertiary, borderRadius: 3, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 3 },

  emptyBlock: {
    alignItems: 'center', gap: spacing.md,
    marginTop: spacing.xxxl, paddingHorizontal: spacing.xl,
  },
  emptyIcon: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: colors.brandTertiary,
    borderWidth: 1, borderColor: colors.brand,
    alignItems: 'center', justifyContent: 'center',
  },
  emptyTitle: { color: colors.onSurface, fontSize: 18, fontWeight: '700' },
  emptySub: { color: colors.onSurfaceTertiary, fontSize: 13, textAlign: 'center', lineHeight: 18 },
  emptyBtn: {
    flexDirection: 'row', gap: 6, alignItems: 'center',
    backgroundColor: colors.brand,
    paddingHorizontal: spacing.lg, paddingVertical: 12,
    borderRadius: radius.md, marginTop: spacing.sm,
  },
  emptyBtnText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: '700' },

  // Modal
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.65)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: colors.surfaceSecondary,
    borderTopLeftRadius: 24, borderTopRightRadius: 24,
    borderTopWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
    maxHeight: '90%',
  },
  grabber: {
    width: 36, height: 4, borderRadius: 2,
    backgroundColor: colors.surfaceTertiary,
    alignSelf: 'center', marginTop: spacing.sm,
  },
  modalHead: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  modalKicker: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1.4, fontWeight: '700' },
  modalTitle: { color: colors.onSurface, fontSize: 18, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.surfaceTertiary,
    alignItems: 'center', justifyContent: 'center',
  },
  modalBody: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },

  label: {
    color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1.2,
    fontWeight: '700', marginTop: spacing.md, marginBottom: spacing.sm,
  },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.lg },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: spacing.md, paddingVertical: 8, borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    backgroundColor: colors.surfaceTertiary,
  },
  chipText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: '600' },

  input: {
    color: colors.onSurface, fontSize: 14,
    backgroundColor: colors.surfaceTertiary,
    borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 12,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  numRow: { flexDirection: 'row', gap: spacing.md },
  numCol: { flex: 1 },

  errBox: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: spacing.md, padding: spacing.sm, borderRadius: radius.sm,
    backgroundColor: 'rgba(229,72,77,0.10)',
    borderWidth: StyleSheet.hairlineWidth, borderColor: 'rgba(229,72,77,0.3)',
  },
  errText: { color: colors.error, fontSize: 12, flex: 1 },

  saveBtn: {
    marginTop: spacing.lg,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: radius.md, paddingVertical: 14,
  },
  saveBtnText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: '700' },
  hint: { color: colors.onSurfaceTertiary, fontSize: 11, textAlign: 'center', marginTop: spacing.md },
});
