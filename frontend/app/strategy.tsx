import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const HORIZONS = [30, 60, 90];

function PlanView({ plan, onToggle }: { plan: any; onToggle: (phase: number, kind: string, task: number, checked: boolean) => void }) {
  if (!plan) return null;
  const progress = plan.task_progress || {};
  const isDone = (phase: number, kind: string, task: number) => !!progress[`${phase}.${kind}.${task}`];
  return (
    <View style={{ gap: spacing.lg }}>
      <View style={styles.planHero}>
        <Text style={styles.planKicker}>{plan.horizon_days}-DAY ROADMAP</Text>
        <Text style={styles.planTitle}>{plan.title}</Text>
        <Text style={styles.planSummary}>{plan.summary}</Text>
        {typeof plan.progress_pct === 'number' && plan.progress_pct > 0 && (
          <View style={styles.progressWrap}>
            <View style={styles.progressBg}>
              <View style={[styles.progressFill, { width: `${plan.progress_pct}%` }]} />
            </View>
            <Text style={styles.progressText}>{plan.progress_pct}% complete</Text>
          </View>
        )}
        {plan.north_star && (
          <View style={styles.northStar}>
            <Ionicons name="star" size={12} color={colors.brand} />
            <View style={{ flex: 1 }}>
              <Text style={styles.northStarLabel}>NORTH STAR · {plan.north_star.metric}</Text>
              <Text style={styles.northStarValue}>{plan.north_star.target}</Text>
            </View>
          </View>
        )}
      </View>

      {plan.kpis?.length > 0 && (
        <View style={styles.block}>
          <Text style={styles.blockTitle}>KPIs</Text>
          {plan.kpis.map((k: any, i: number) => (
            <View key={i} style={styles.kpiRow}>
              <View style={styles.kpiDot} />
              <View style={{ flex: 1 }}>
                <Text style={styles.kpiLabel}>{k.label}</Text>
                <Text style={styles.kpiTarget}>{k.target}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {plan.phases?.map((phase: any, i: number) => (
        <View key={i} style={styles.block}>
          <View style={styles.phaseHeader}>
            <Text style={styles.phaseWindow}>{phase.window}</Text>
            <Text style={styles.phaseTheme}>{phase.theme}</Text>
          </View>
          {phase.milestones?.length > 0 && (
            <View style={styles.subBlock}>
              <Text style={styles.subTitle}>MILESTONES</Text>
              {phase.milestones.map((m: string, j: number) => {
                const done = isDone(i, 'milestones', j);
                return (
                  <Pressable
                    key={j}
                    onPress={() => onToggle(i, 'milestones', j, !done)}
                    style={styles.checkRow}
                    testID={`task-milestone-${i}-${j}`}
                  >
                    <Ionicons
                      name={done ? 'checkmark-circle' : 'ellipse-outline'}
                      size={16}
                      color={done ? colors.success : colors.brand}
                    />
                    <Text style={[styles.checkText, done && styles.checkTextDone]}>{m}</Text>
                  </Pressable>
                );
              })}
            </View>
          )}
          {phase.weekly_tasks?.length > 0 && (
            <View style={styles.subBlock}>
              <Text style={styles.subTitle}>WEEKLY TASKS</Text>
              {phase.weekly_tasks.map((t: string, j: number) => {
                const done = isDone(i, 'weekly_tasks', j);
                return (
                  <Pressable
                    key={j}
                    onPress={() => onToggle(i, 'weekly_tasks', j, !done)}
                    style={styles.checkRow}
                    testID={`task-weekly-${i}-${j}`}
                  >
                    <Ionicons
                      name={done ? 'checkbox' : 'square-outline'}
                      size={15}
                      color={done ? colors.success : colors.onSurfaceSecondary}
                    />
                    <Text style={[styles.checkText, done && styles.checkTextDone]}>{t}</Text>
                  </Pressable>
                );
              })}
            </View>
          )}
          {phase.risk && (
            <View style={styles.riskRow}>
              <Ionicons name="warning-outline" size={13} color={colors.warning} />
              <Text style={styles.riskText}>{phase.risk}</Text>
            </View>
          )}
        </View>
      ))}

      {plan.leading_indicators?.length > 0 && (
        <View style={styles.block}>
          <Text style={styles.blockTitle}>Leading indicators</Text>
          {plan.leading_indicators.map((s: string, i: number) => (
            <View key={i} style={styles.checkRow}>
              <Ionicons name="trending-up" size={13} color={colors.success} />
              <Text style={styles.checkText}>{s}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

export default function Strategy() {
  const router = useRouter();
  const [horizon, setHorizon] = useState(60);
  const [plan, setPlan] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  const loadHistory = async () => {
    try {
      const r = await api.strategyList();
      setHistory(r.items);
      if (r.items.length && !plan) setPlan(r.items[0]);
    } catch (e) { console.warn(e); }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadHistory(); }, []);

  const generate = async () => {
    setBusy(true);
    try {
      const p = await api.strategyGenerate(horizon);
      setPlan(p);
      await loadHistory();
    } catch (e) {
      console.warn(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} testID="back-btn">
            <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>AI STRATEGY PLANNER</Text>
            <Text style={styles.title}>Your roadmap</Text>
          </View>
        </View>

        <View style={styles.controls}>
          <View style={styles.horizonRow}>
            {HORIZONS.map(h => (
              <Pressable
                key={h}
                onPress={() => setHorizon(h)}
                style={[styles.horizonChip, horizon === h && styles.horizonChipActive]}
                testID={`horizon-${h}`}
              >
                <Text style={[styles.horizonText, horizon === h && styles.horizonTextActive]}>{h}-day</Text>
              </Pressable>
            ))}
          </View>
          <Pressable
            onPress={generate}
            disabled={busy}
            style={[styles.genBtn, busy && { opacity: 0.6 }]}
            testID="generate-plan-btn"
          >
            {busy
              ? <ActivityIndicator color={colors.onBrandPrimary} size="small" />
              : <Ionicons name="sparkles" size={16} color={colors.onBrandPrimary} />
            }
            <Text style={styles.genBtnText}>{busy ? 'Generating…' : 'Generate plan'}</Text>
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        {!plan && !busy && (
          <View style={styles.empty} testID="strategy-empty">
            <View style={styles.emptyIcon}><Ionicons name="map-outline" size={32} color={colors.brand} /></View>
            <Text style={styles.emptyTitle}>Generate your first plan</Text>
            <Text style={styles.emptySub}>Tap &quot;Generate plan&quot; — the AI will draft a quantified roadmap from your business context.</Text>
          </View>
        )}
        {busy && !plan && (
          <View style={styles.empty}>
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.emptySub}>Drafting your roadmap with Claude Sonnet 4.5…</Text>
          </View>
        )}
        {plan && (
          <PlanView
            plan={plan}
            onToggle={async (phase, kind, task, checked) => {
              // optimistic update
              const key = `${phase}.${kind}.${task}`;
              const updated = { ...plan, task_progress: { ...(plan.task_progress || {}) } };
              if (checked) updated.task_progress[key] = true;
              else delete updated.task_progress[key];
              setPlan(updated);
              try {
                const r = await api.strategyToggleTask(plan.id, phase, kind, task, checked);
                setPlan({ ...updated, task_progress: r.task_progress, progress_pct: r.progress_pct });
              } catch {
                // revert on error
                setPlan(plan);
              }
            }}
          />
        )}
        {history.length > 1 && (
          <View style={styles.historySection}>
            <Text style={styles.historyTitle}>Past plans</Text>
            {history.slice(1, 5).map((p: any) => (
              <Pressable key={p.id} onPress={() => setPlan(p)} style={styles.historyRow} testID={`history-${p.id}`}>
                <Text style={styles.historyText} numberOfLines={1}>{p.title}</Text>
                <Text style={styles.historyMeta}>{p.horizon_days}d · {(p.created_at || '').slice(0, 10)}</Text>
              </Pressable>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md },
  backBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.surfaceSecondary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  kicker: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600' },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },

  controls: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md, gap: spacing.sm },
  horizonRow: { flexDirection: 'row', gap: spacing.sm },
  horizonChip: { paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radius.pill, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  horizonChipActive: { backgroundColor: colors.brandTertiary, borderColor: colors.brand },
  horizonText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: '600' },
  horizonTextActive: { color: colors.brand },
  genBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: radius.md, paddingVertical: 12,
  },
  genBtnText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: '700' },

  empty: { alignItems: 'center', paddingVertical: spacing.xxxl, gap: spacing.md },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.brandTertiary, alignItems: 'center', justifyContent: 'center', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand },
  emptyTitle: { color: colors.onSurface, fontSize: 18, fontWeight: '600' },
  emptySub: { color: colors.onSurfaceSecondary, fontSize: 13, textAlign: 'center', maxWidth: 280 },

  planHero: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  planKicker: { color: colors.brand, fontSize: 11, letterSpacing: 1.4, fontWeight: '700' },
  planTitle: { color: colors.onSurface, fontSize: 18, fontWeight: '600', marginTop: 4, letterSpacing: -0.3, lineHeight: 24 },
  planSummary: { color: colors.onSurfaceSecondary, fontSize: 13, marginTop: spacing.sm, lineHeight: 19 },
  northStar: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.divider,
  },
  northStarLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '700' },
  northStarValue: { color: colors.onSurface, fontSize: 14, fontWeight: '600', marginTop: 2 },

  block: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  blockTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },
  kpiRow: { flexDirection: 'row', gap: spacing.md, paddingVertical: spacing.sm, alignItems: 'flex-start' },
  kpiDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.brand, marginTop: 6 },
  kpiLabel: { color: colors.onSurface, fontSize: 13, fontWeight: '500' },
  kpiTarget: { color: colors.brand, fontSize: 12, marginTop: 2 },

  phaseHeader: { marginBottom: spacing.md },
  phaseWindow: { color: colors.brand, fontSize: 11, letterSpacing: 1.4, fontWeight: '700' },
  phaseTheme: { color: colors.onSurface, fontSize: 15, fontWeight: '600', marginTop: 4, letterSpacing: -0.2 },

  subBlock: { marginTop: spacing.md },
  subTitle: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1.2, fontWeight: '700', marginBottom: spacing.sm },
  checkRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start', paddingVertical: 6 },
  checkText: { color: colors.onSurface, fontSize: 13, lineHeight: 19, flex: 1 },
  checkTextDone: { color: colors.onSurfaceTertiary, textDecorationLine: 'line-through' },

  progressWrap: { marginTop: spacing.md, gap: 6 },
  progressBg: { height: 4, backgroundColor: colors.surfaceTertiary, borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: colors.success },
  progressText: { color: colors.success, fontSize: 11, fontWeight: '600' },

  riskRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.divider,
  },
  riskText: { color: colors.onSurfaceSecondary, fontSize: 12, flex: 1, lineHeight: 18 },

  historySection: { marginTop: spacing.xl },
  historyTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },
  historyRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  historyText: { color: colors.onSurface, fontSize: 13, flex: 1 },
  historyMeta: { color: colors.onSurfaceTertiary, fontSize: 11, marginLeft: spacing.sm },
});
