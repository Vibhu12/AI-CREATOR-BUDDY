import { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fmtCompact } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const KIND_ICON: Record<string, any> = {
  revenue: 'cash-outline',
  followers: 'people-outline',
  subscribers: 'play-circle-outline',
  launch: 'rocket-outline',
  content: 'film-outline',
};

function GoalCard({ goal }: { goal: any }) {
  const pct = Math.min(100, Math.round((goal.current / goal.target) * 100));
  const display = goal.kind === 'revenue' ? `$${fmtCompact(goal.current)} / $${fmtCompact(goal.target)}`
    : goal.kind === 'launch' ? `${Math.round(goal.current * 100)}%`
    : `${fmtCompact(goal.current)} / ${fmtCompact(goal.target)}`;
  return (
    <View style={styles.card} testID={`goal-${goal.id}`}>
      <View style={styles.cardHead}>
        <View style={styles.cardIcon}>
          <Ionicons name={KIND_ICON[goal.kind] ?? 'flag-outline'} size={16} color={colors.brand} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitle}>{goal.title}</Text>
          <Text style={styles.cardSub}>{display}</Text>
        </View>
        <Text style={styles.pct}>{pct}%</Text>
      </View>
      <View style={styles.barBg}>
        <View style={[styles.barFill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

export default function Profile() {
  const [goals, setGoals] = useState<any[]>([]);
  const [content, setContent] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const [g, c] = await Promise.all([api.goals(), api.content()]);
      setGoals(g.items);
      setContent(c.items);
    } catch (e) { console.warn(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Text style={styles.kicker}>PROFILE</Text>
          <Text style={styles.title}>Maya Chen</Text>
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <View style={styles.heroBlock}>
          <View style={styles.bigAvatar}>
            <Text style={styles.bigAvatarText}>MC</Text>
          </View>
          <Text style={styles.fullName}>Maya Chen</Text>
          <Text style={styles.handle}>@mayabuilds · Creator, founder</Text>
          <View style={styles.proPill}>
            <Ionicons name="star" size={11} color={colors.brand} />
            <Text style={styles.proPillText}>CreatorOS Pro</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Active goals</Text>
          {goals.map(g => <GoalCard key={g.id} goal={g} />)}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Top content this month</Text>
          {content.slice(0, 4).map((c: any) => (
            <View key={c.id} style={styles.contentRow} testID={`content-${c.id}`}>
              <View style={styles.contentLeft}>
                <Text style={styles.contentTitle} numberOfLines={2}>{c.title}</Text>
                <Text style={styles.contentMeta}>{c.platform.toUpperCase()} · {fmtCompact(c.views)} views</Text>
              </View>
              <View style={styles.viralityBox}>
                <Text style={styles.viralityScore}>{c.virality}</Text>
                <Text style={styles.viralityLabel}>VIRAL</Text>
              </View>
            </View>
          ))}
        </View>

        <View style={styles.section}>
          {[
            { icon: 'link-outline', label: 'Connected integrations', value: '12' },
            { icon: 'shield-checkmark-outline', label: 'Security', value: '2FA on' },
            { icon: 'color-palette-outline', label: 'Appearance', value: 'Dark' },
            { icon: 'help-circle-outline', label: 'Help & support', value: '' },
          ].map((item, i) => (
            <Pressable key={i} style={styles.settingRow} testID={`setting-${i}`}>
              <Ionicons name={item.icon as any} size={18} color={colors.onSurfaceSecondary} />
              <Text style={styles.settingLabel}>{item.label}</Text>
              <Text style={styles.settingValue}>{item.value}</Text>
              <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceTertiary} />
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md },
  kicker: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600' },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },

  heroBlock: { alignItems: 'center', paddingVertical: spacing.lg, gap: spacing.sm },
  bigAvatar: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: colors.brandTertiary,
    borderWidth: 1, borderColor: colors.brand,
    alignItems: 'center', justifyContent: 'center',
  },
  bigAvatarText: { color: colors.brand, fontSize: 24, fontWeight: '700' },
  fullName: { color: colors.onSurface, fontSize: 18, fontWeight: '600', marginTop: spacing.sm },
  handle: { color: colors.onSurfaceTertiary, fontSize: 12 },
  proPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: colors.brandTertiary,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill, marginTop: spacing.sm,
  },
  proPillText: { color: colors.brand, fontSize: 11, fontWeight: '700', letterSpacing: 0.4 },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.xl },
  sectionTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },

  card: {
    backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, marginBottom: spacing.sm,
  },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginBottom: spacing.md },
  cardIcon: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: colors.brandTertiary,
    alignItems: 'center', justifyContent: 'center',
  },
  cardTitle: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  cardSub: { color: colors.onSurfaceTertiary, fontSize: 12, marginTop: 2 },
  pct: { color: colors.brand, fontSize: 14, fontWeight: '700' },
  barBg: { height: 4, backgroundColor: colors.surfaceTertiary, borderRadius: 2, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: colors.brand },

  contentRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  contentLeft: { flex: 1 },
  contentTitle: { color: colors.onSurface, fontSize: 13, fontWeight: '500', lineHeight: 18 },
  contentMeta: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 4, letterSpacing: 0.4 },
  viralityBox: { alignItems: 'center', minWidth: 40 },
  viralityScore: { color: colors.brand, fontSize: 20, fontWeight: '700', letterSpacing: -0.5 },
  viralityLabel: { color: colors.onSurfaceTertiary, fontSize: 9, letterSpacing: 0.8, fontWeight: '700' },

  settingRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  settingLabel: { color: colors.onSurface, fontSize: 14, flex: 1 },
  settingValue: { color: colors.onSurfaceTertiary, fontSize: 12 },
});
