import { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fmtCompact } from '@/src/theme/tokens';
import { api } from '@/src/services/api';
import { useAuth } from '@/src/auth/AuthContext';

const KIND_ICON: Record<string, any> = {
  revenue: 'cash-outline',
  followers: 'people-outline',
  subscribers: 'play-circle-outline',
  launch: 'rocket-outline',
  content: 'film-outline',
};

const INTEGRATION_ICON: Record<string, any> = {
  youtube: 'logo-youtube',
  instagram: 'logo-instagram',
  stripe: 'card',
  paypal: 'wallet',
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
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [goals, setGoals] = useState<any[]>([]);
  const [content, setContent] = useState<any[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [reseeding, setReseeding] = useState(false);

  const load = useCallback(async () => {
    try {
      const [g, c, conn] = await Promise.all([api.goals(), api.content(), api.connections()]);
      setGoals(g.items);
      setContent(c.items);
      setConnections(conn.connections);
    } catch (e) { console.warn(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const initials = (user?.name ?? 'Maya Chen')
    .split(' ').slice(0, 2).map(s => s[0]?.toUpperCase()).join('');

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Text style={styles.kicker}>PROFILE</Text>
          <Text style={styles.title}>{user?.name ?? 'Maya Chen'}</Text>
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <View style={styles.heroBlock}>
          {user?.picture
            ? <Image source={{ uri: user.picture }} style={styles.bigAvatarImg} />
            : <View style={styles.bigAvatar}><Text style={styles.bigAvatarText}>{initials || 'MC'}</Text></View>
          }
          <Text style={styles.fullName}>{user?.name ?? 'Maya Chen'}</Text>
          <Text style={styles.handle}>{user?.email ?? '@mayabuilds · Creator, founder'}</Text>
          <Pressable onPress={() => router.push('/pricing')} style={styles.tierPill} testID="tier-badge">
            <Ionicons name="star" size={11} color={colors.brand} />
            <Text style={styles.tierPillText}>
              CreatorOS {user?.tier ? user.tier.charAt(0).toUpperCase() + user.tier.slice(1) : 'Free'}
            </Text>
            {(!user?.tier || user.tier === 'free') && (
              <Text style={styles.upgradeHint}> · Upgrade</Text>
            )}
          </Pressable>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Active goals</Text>
          {goals.map(g => <GoalCard key={g.id} goal={g} />)}
        </View>

        <View style={styles.section}>
          <View style={styles.sectionHeadRow}>
            <Text style={styles.sectionTitle}>Connected integrations</Text>
            <Pressable onPress={() => router.push('/integrations')} testID="manage-integrations">
              <Text style={styles.sectionLink}>
                Manage <Ionicons name="chevron-forward" size={11} color={colors.brand} />
              </Text>
            </Pressable>
          </View>
          <Pressable
            onPress={() => router.push('/integrations')}
            style={styles.connectionsCard}
            testID="connections-summary"
          >
            <View style={styles.connIconsRow}>
              {connections.map(c => (
                <View
                  key={c.id}
                  style={[
                    styles.connIcon,
                    {
                      backgroundColor: `${c.color}22`,
                      borderColor: c.connected ? c.color : colors.borderStrong,
                      opacity: c.connected ? 1 : 0.4,
                    },
                  ]}
                >
                  <Ionicons
                    name={INTEGRATION_ICON[c.id] ?? 'apps'}
                    size={16}
                    color={c.connected ? c.color : colors.onSurfaceTertiary}
                  />
                </View>
              ))}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.connSummary}>
                {connections.filter(c => c.connected).length} of {connections.length} connected
              </Text>
              <Text style={styles.connSummarySub}>
                {connections.filter(c => c.connected).length === 0
                  ? 'Connect YouTube, Instagram, Stripe, PayPal'
                  : connections.filter(c => c.connected).map(c => c.name).join(' · ')}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
          </Pressable>
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
          <Pressable
            onPress={async () => {
              setReseeding(true);
              try { await api.reseedStarter(); await load(); } finally { setReseeding(false); }
            }}
            disabled={reseeding}
            style={[styles.reseedBtn, reseeding && { opacity: 0.6 }]}
            testID="reseed-btn"
          >
            <Ionicons name="refresh-circle-outline" size={18} color={colors.brand} />
            <Text style={styles.reseedText}>
              {reseeding ? 'Reloading…' : 'Reload Maya demo data'}
            </Text>
          </Pressable>

          <Pressable onPress={signOut} style={[styles.signOutBtn, { marginTop: spacing.sm }]} testID="sign-out-btn">
            <Ionicons name="log-out-outline" size={18} color={colors.error} />
            <Text style={styles.signOutText}>Sign out</Text>
          </Pressable>
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
  bigAvatarImg: {
    width: 72, height: 72, borderRadius: 36,
    borderWidth: 1, borderColor: colors.brand,
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
  tierPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: colors.brandTertiary,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, marginTop: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  tierPillText: { color: colors.brand, fontSize: 11, fontWeight: '700', letterSpacing: 0.4 },
  upgradeHint: { color: colors.onSurface, fontSize: 11, fontWeight: '600' },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.xl },
  sectionTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },
  sectionHeadRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: spacing.md,
  },
  sectionLink: { color: colors.brand, fontSize: 12, fontWeight: '600' },

  connectionsCard: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  connIconsRow: { flexDirection: 'row', gap: -6 },
  connIcon: {
    width: 34, height: 34, borderRadius: 17,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1.5, marginRight: -8,
  },
  connSummary: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  connSummarySub: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 2 },

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

  intRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  intIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  intLabel: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  intMeta: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 2 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },

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

  signOutBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: 'rgba(229,72,77,0.08)',
    borderRadius: radius.md, paddingVertical: 14,
    borderWidth: StyleSheet.hairlineWidth, borderColor: 'rgba(229,72,77,0.3)',
  },
  signOutText: { color: colors.error, fontSize: 14, fontWeight: '600' },

  reseedBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.md, paddingVertical: 14,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  reseedText: { color: colors.brand, fontSize: 14, fontWeight: '600' },
});
