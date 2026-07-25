import { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator,
  Modal, TextInput, KeyboardAvoidingView, Platform, RefreshControl, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, fmtCompact, fmtCurrency } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

type Provider = {
  id: 'youtube' | 'instagram' | 'stripe' | 'paypal';
  name: string;
  description: string;
  color: string;
  input_label: string;
  input_placeholder: string;
  input_prefix: string | null;
  connected: boolean;
  account: string | null;
  connected_at: string | null;
  summary: { label: string; primary_metric: string; secondary_metric: string } | null;
};

const ICONS: Record<string, any> = {
  youtube: 'logo-youtube',
  instagram: 'logo-instagram',
  stripe: 'card',
  paypal: 'wallet',
};

export default function IntegrationsHub() {
  const router = useRouter();
  const [items, setItems] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [connectTarget, setConnectTarget] = useState<Provider | null>(null);
  const [detailTarget, setDetailTarget] = useState<Provider | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.connections();
      setItems(r.connections);
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

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} testID="back-btn">
            <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>CONNECTIONS</Text>
            <Text style={styles.title}>Integrations</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={styles.summaryCard}>
          <View style={styles.summaryLeft}>
            <Text style={styles.summaryLabel}>Connected accounts</Text>
            <Text style={styles.summaryValue}>
              {items.filter(i => i.connected).length}
              <Text style={styles.summaryValueMuted}> / {items.length}</Text>
            </Text>
          </View>
          <View style={styles.summaryPill}>
            <Ionicons name="shield-checkmark" size={13} color={colors.brand} />
            <Text style={styles.summaryPillText}>Read-only sync</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Available integrations</Text>

        {loading ? (
          <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.xl }} />
        ) : (
          <View style={{ gap: spacing.md }}>
            {items.map(p => (
              <ProviderCard
                key={p.id}
                provider={p}
                onConnect={() => setConnectTarget(p)}
                onView={() => setDetailTarget(p)}
                onDisconnect={async () => {
                  try {
                    await api.disconnectProvider(p.id);
                    await load();
                  } catch (e) {
                    console.warn(e);
                  }
                }}
              />
            ))}
          </View>
        )}

        <View style={styles.note}>
          <Ionicons name="information-circle-outline" size={14} color={colors.onSurfaceTertiary} />
          <Text style={styles.noteText}>
            Live connections use OAuth-style handshake. Data shown for demo accounts is generated
            deterministically from your handle — plug in real API keys later to switch to live data.
          </Text>
        </View>
      </ScrollView>

      <ConnectModal
        provider={connectTarget}
        onClose={() => setConnectTarget(null)}
        onConnected={async () => {
          setConnectTarget(null);
          await load();
        }}
      />

      <DetailModal
        provider={detailTarget}
        onClose={() => setDetailTarget(null)}
      />
    </View>
  );
}


function ProviderCard({
  provider, onConnect, onView, onDisconnect,
}: {
  provider: Provider;
  onConnect: () => void;
  onView: () => void;
  onDisconnect: () => void;
}) {
  return (
    <View style={styles.pcard} testID={`provider-${provider.id}`}>
      <View style={styles.pcardTop}>
        <View style={[styles.pcardIcon, { backgroundColor: `${provider.color}22`, borderColor: `${provider.color}55` }]}>
          <Ionicons name={ICONS[provider.id]} size={20} color={provider.color} />
        </View>
        <View style={{ flex: 1 }}>
          <View style={styles.pcardHeadRow}>
            <Text style={styles.pcardName}>{provider.name}</Text>
            {provider.connected && (
              <View style={styles.connectedPill}>
                <View style={[styles.pulse, { backgroundColor: colors.success }]} />
                <Text style={styles.connectedPillText}>Connected</Text>
              </View>
            )}
          </View>
          <Text style={styles.pcardDesc} numberOfLines={2}>{provider.description}</Text>
        </View>
      </View>

      {provider.connected && provider.summary && (
        <View style={styles.pcardMetrics}>
          <View style={styles.pcardMetric}>
            <Text style={styles.pcardMetricValue}>{provider.summary.primary_metric}</Text>
            <Text style={styles.pcardMetricLabel}>{provider.summary.label}</Text>
          </View>
          <View style={styles.pcardVsep} />
          <View style={styles.pcardMetric}>
            <Text style={styles.pcardMetricValue}>{provider.summary.secondary_metric}</Text>
            <Text style={styles.pcardMetricLabel}>this month</Text>
          </View>
        </View>
      )}

      <View style={styles.pcardActions}>
        {provider.connected ? (
          <>
            <Pressable
              onPress={onView}
              style={[styles.actionBtn, { flex: 1 }]}
              testID={`view-${provider.id}`}
            >
              <Ionicons name="analytics-outline" size={15} color={colors.onSurface} />
              <Text style={styles.actionBtnText}>View data</Text>
            </Pressable>
            <Pressable
              onPress={() => {
                Alert.alert(
                  `Disconnect ${provider.name}?`,
                  'You can reconnect anytime. Your CreatorOS data stays intact.',
                  [
                    { text: 'Cancel', style: 'cancel' },
                    { text: 'Disconnect', style: 'destructive', onPress: onDisconnect },
                  ],
                );
              }}
              style={styles.actionBtnGhost}
              testID={`disconnect-${provider.id}`}
            >
              <Ionicons name="close" size={16} color={colors.error} />
            </Pressable>
          </>
        ) : (
          <Pressable
            onPress={onConnect}
            style={[styles.actionBtn, styles.actionBtnPrimary, { flex: 1, backgroundColor: provider.color }]}
            testID={`connect-${provider.id}`}
          >
            <Ionicons name="link" size={15} color="#fff" />
            <Text style={[styles.actionBtnText, { color: '#fff' }]}>Connect {provider.name}</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}


// ---------------------------------------------------------------------------
// Connect modal — simulates OAuth handshake
// ---------------------------------------------------------------------------
type Phase = 'input' | 'redirect' | 'authorizing' | 'success';

function ConnectModal({
  provider, onClose, onConnected,
}: {
  provider: Provider | null;
  onClose: () => void;
  onConnected: () => void;
}) {
  const [account, setAccount] = useState('');
  const [phase, setPhase] = useState<Phase>('input');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    if (provider) {
      setAccount('');
      setPhase('input');
      setError(null);
      setResult(null);
    }
  }, [provider]);

  if (!provider) return null;

  const submit = async () => {
    const trimmed = account.trim();
    if (!trimmed) {
      setError(`Please enter your ${provider.input_label.toLowerCase()}`);
      return;
    }
    if ((provider.id === 'stripe' || provider.id === 'paypal') && !/^\S+@\S+\.\S+$/.test(trimmed)) {
      setError('Please enter a valid email');
      return;
    }
    setError(null);
    setPhase('redirect');
    await new Promise(r => setTimeout(r, 500));
    setPhase('authorizing');
    try {
      const r = await api.connectProvider(provider.id, trimmed);
      setResult(r.connection);
      setPhase('success');
      await new Promise(r => setTimeout(r, 900));
      onConnected();
    } catch (e: any) {
      setError(e?.message ?? 'Connection failed');
      setPhase('input');
    }
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ width: '100%', alignItems: 'center' }}
        >
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <View style={[styles.modalIcon, { backgroundColor: `${provider.color}22`, borderColor: `${provider.color}55` }]}>
                <Ionicons name={ICONS[provider.id]} size={22} color={provider.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.modalTitle}>Connect {provider.name}</Text>
                <Text style={styles.modalSub}>{provider.description}</Text>
              </View>
              <Pressable onPress={onClose} style={styles.modalClose} testID="modal-close">
                <Ionicons name="close" size={20} color={colors.onSurfaceSecondary} />
              </Pressable>
            </View>

            {phase === 'input' && (
              <View style={{ gap: spacing.md, marginTop: spacing.lg }}>
                <View>
                  <Text style={styles.inputLabel}>{provider.input_label}</Text>
                  <View style={styles.inputRow}>
                    {provider.input_prefix && <Text style={styles.inputPrefix}>{provider.input_prefix}</Text>}
                    <TextInput
                      value={account}
                      onChangeText={(t) => { setAccount(t); if (error) setError(null); }}
                      placeholder={provider.input_placeholder.replace(/^@/, '')}
                      placeholderTextColor={colors.onSurfaceTertiary}
                      style={styles.input}
                      autoCapitalize="none"
                      autoCorrect={false}
                      keyboardType={provider.input_prefix ? 'default' : 'email-address'}
                      testID="connect-input"
                    />
                  </View>
                  {error && <Text style={styles.errorText}>{error}</Text>}
                </View>

                <View style={styles.permissionBox}>
                  <Text style={styles.permissionTitle}>CreatorOS will access:</Text>
                  {permissionsFor(provider.id).map((p, i) => (
                    <View key={i} style={styles.permRow}>
                      <Ionicons name="checkmark-circle" size={13} color={colors.brand} />
                      <Text style={styles.permText}>{p}</Text>
                    </View>
                  ))}
                </View>

                <Pressable
                  onPress={submit}
                  style={[styles.submitBtn, { backgroundColor: provider.color }]}
                  testID="connect-submit"
                >
                  <Ionicons name="lock-closed" size={14} color="#fff" />
                  <Text style={styles.submitBtnText}>Authorize {provider.name}</Text>
                </Pressable>
                <Text style={styles.disclaimer}>
                  Read-only. We never post on your behalf. Disconnect anytime.
                </Text>
              </View>
            )}

            {(phase === 'redirect' || phase === 'authorizing') && (
              <View style={styles.progressBlock}>
                <ActivityIndicator size="large" color={provider.color} />
                <Text style={styles.progressTitle}>
                  {phase === 'redirect' ? `Redirecting to ${provider.name}…` : `Authorizing…`}
                </Text>
                <Text style={styles.progressSub}>
                  {phase === 'redirect'
                    ? `Opening secure ${provider.name} sign-in`
                    : `Fetching your account details`}
                </Text>
              </View>
            )}

            {phase === 'success' && (
              <View style={styles.progressBlock}>
                <View style={[styles.successCircle, { backgroundColor: `${colors.success}22`, borderColor: `${colors.success}66` }]}>
                  <Ionicons name="checkmark" size={32} color={colors.success} />
                </View>
                <Text style={styles.progressTitle}>Connected!</Text>
                {result?.summary && (
                  <Text style={styles.progressSub}>
                    {result.summary.label} · {result.summary.primary_metric}
                  </Text>
                )}
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}


function permissionsFor(providerId: string): string[] {
  switch (providerId) {
    case 'youtube':
      return ['Channel stats (subscribers, views, videos)', 'Recent video performance', 'Estimated monthly revenue'];
    case 'instagram':
      return ['Profile stats (followers, posts)', 'Recent reel performance', 'Engagement + reach metrics'];
    case 'stripe':
      return ['Available + pending balances', 'Recent charges + payouts', 'Subscription revenue'];
    case 'paypal':
      return ['Available balance', 'Recent transactions', 'Cross-border payment mix'];
    default:
      return [];
  }
}


// ---------------------------------------------------------------------------
// Detail modal — shows full stats for a connected provider
// ---------------------------------------------------------------------------
function DetailModal({ provider, onClose }: { provider: Provider | null; onClose: () => void }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!provider) { setData(null); return; }
    setLoading(true);
    (async () => {
      try {
        let r: any;
        if (provider.id === 'youtube') r = await api.youtubeChannel();
        else if (provider.id === 'instagram') r = await api.instagramProfile();
        else if (provider.id === 'stripe') r = await api.stripeStatus();
        else if (provider.id === 'paypal') r = await api.paypalStatus();
        setData(r);
      } catch (e) {
        console.warn(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [provider]);

  if (!provider) return null;

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.detailBackdrop}>
        <View style={styles.detailSheet}>
          <View style={styles.detailHandle} />
          <View style={styles.detailHeader}>
            <View style={[styles.modalIcon, { backgroundColor: `${provider.color}22`, borderColor: `${provider.color}55` }]}>
              <Ionicons name={ICONS[provider.id]} size={20} color={provider.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.modalTitle}>{provider.name}</Text>
              <Text style={styles.modalSub}>{provider.summary?.label ?? provider.account}</Text>
            </View>
            <Pressable onPress={onClose} style={styles.modalClose} testID="detail-close">
              <Ionicons name="close" size={20} color={colors.onSurfaceSecondary} />
            </Pressable>
          </View>

          {loading ? (
            <ActivityIndicator color={provider.color} style={{ marginTop: spacing.xl }} />
          ) : data ? (
            <ScrollView style={{ marginTop: spacing.lg }} showsVerticalScrollIndicator={false}>
              {renderProviderDetail(provider.id, data)}
              <View style={{ height: 60 }} />
            </ScrollView>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}


function renderProviderDetail(id: string, d: any) {
  if (id === 'youtube') {
    return (
      <View style={{ gap: spacing.md }}>
        <StatGrid stats={[
          { label: 'Subscribers', value: fmtCompact(d.subscribers) },
          { label: 'Total views', value: fmtCompact(d.views) },
          { label: 'Videos', value: fmtCompact(d.videos) },
          { label: 'Est. RPM', value: `$${d.avg_rpm}` },
          { label: 'Avg CTR', value: `${d.avg_ctr}%` },
          { label: 'Watch time', value: `${d.avg_watch_pct}%` },
        ]} />
        <View style={styles.card}>
          <Text style={styles.cardKicker}>MONTHLY EARNINGS</Text>
          <Text style={styles.cardBig}>{fmtCurrency(d.monthly_earnings)}</Text>
          <Text style={styles.cardHint}>Estimated via avg RPM × 30-day views</Text>
        </View>
        <RecentList
          title="Recent videos"
          items={(d.recent_videos ?? []).map((v: any) => ({
            primary: v.title,
            secondary: `${fmtCompact(v.views)} views · ${fmtCompact(v.likes)} likes`,
          }))}
        />
      </View>
    );
  }
  if (id === 'instagram') {
    return (
      <View style={{ gap: spacing.md }}>
        <StatGrid stats={[
          { label: 'Followers', value: fmtCompact(d.followers) },
          { label: 'Following', value: fmtCompact(d.following) },
          { label: 'Posts', value: fmtCompact(d.posts) },
          { label: 'Engagement', value: `${d.engagement_rate}%` },
          { label: 'Avg reel views', value: fmtCompact(d.avg_reel_views) },
          { label: 'Story compl.', value: `${d.story_completion_rate}%` },
        ]} />
        <View style={styles.card}>
          <Text style={styles.cardKicker}>MONTHLY REACH</Text>
          <Text style={styles.cardBig}>{fmtCompact(d.monthly_reach)}</Text>
          <Text style={styles.cardHint}>Unique accounts reached in the last 30 days</Text>
        </View>
        <RecentList
          title="Recent reels"
          items={(d.recent_reels ?? []).map((r: any) => ({
            primary: r.caption,
            secondary: `${fmtCompact(r.views)} views · ${fmtCompact(r.likes)} likes · ${fmtCompact(r.comments)} comments`,
          }))}
        />
      </View>
    );
  }
  if (id === 'stripe') {
    return (
      <View style={{ gap: spacing.md }}>
        <StatGrid stats={[
          { label: 'Available', value: fmtCurrency(d.available_balance ?? 0) },
          { label: 'Pending', value: fmtCurrency(d.pending_balance ?? 0) },
        ]} />
        <RecentList
          title="Recent charges"
          items={(d.recent_charges ?? []).map((c: any) => ({
            primary: c.description,
            secondary: `${fmtCurrency(c.amount)} · ${c.status}`,
          }))}
        />
      </View>
    );
  }
  if (id === 'paypal') {
    return (
      <View style={{ gap: spacing.md }}>
        <StatGrid stats={[
          { label: 'Available', value: fmtCurrency(d.available_balance ?? 0) },
          { label: 'MTD processed', value: fmtCurrency(d.mtd_processed ?? 0) },
          { label: 'Cross-border', value: `${d.cross_border_pct}%` },
        ]} />
        <RecentList
          title="Recent transactions"
          items={(d.recent_transactions ?? []).map((t: any) => ({
            primary: t.description,
            secondary: `${t.currency} ${t.amount.toFixed(2)} · ${t.buyer}`,
          }))}
        />
      </View>
    );
  }
  return null;
}


function StatGrid({ stats }: { stats: { label: string; value: string }[] }) {
  return (
    <View style={styles.statGrid}>
      {stats.map((s, i) => (
        <View key={i} style={styles.statCell}>
          <Text style={styles.statValue}>{s.value}</Text>
          <Text style={styles.statLabel}>{s.label}</Text>
        </View>
      ))}
    </View>
  );
}


function RecentList({ title, items }: { title: string; items: { primary: string; secondary: string }[] }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardKicker}>{title.toUpperCase()}</Text>
      {items.slice(0, 6).map((it, i) => (
        <View key={i} style={styles.recentRow}>
          <Text style={styles.recentPrimary} numberOfLines={2}>{it.primary}</Text>
          <Text style={styles.recentSecondary}>{it.secondary}</Text>
        </View>
      ))}
    </View>
  );
}


// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
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

  summaryCard: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  summaryLeft: { gap: 2 },
  summaryLabel: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1, fontWeight: '600' },
  summaryValue: { color: colors.onSurface, fontSize: 26, fontWeight: '700', letterSpacing: -1, marginTop: 4 },
  summaryValueMuted: { color: colors.onSurfaceTertiary, fontSize: 18 },
  summaryPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: colors.brandTertiary,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  summaryPillText: { color: colors.brand, fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },

  sectionTitle: {
    color: colors.onSurfaceSecondary, fontSize: 12, letterSpacing: 1.2, fontWeight: '600',
    marginTop: spacing.xl, marginBottom: spacing.md,
  },

  pcard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.md,
  },
  pcardTop: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
  pcardIcon: {
    width: 42, height: 42, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  pcardHeadRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  pcardName: { color: colors.onSurface, fontSize: 16, fontWeight: '700', letterSpacing: -0.2 },
  pcardDesc: { color: colors.onSurfaceTertiary, fontSize: 12, marginTop: 2, lineHeight: 17 },
  connectedPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(69,201,122,0.14)',
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill,
  },
  pulse: { width: 6, height: 6, borderRadius: 3 },
  connectedPillText: { color: colors.success, fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },

  pcardMetrics: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceTertiary,
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
  },
  pcardMetric: { flex: 1, alignItems: 'center' },
  pcardMetricValue: { color: colors.onSurface, fontSize: 14, fontWeight: '700', letterSpacing: -0.3 },
  pcardMetricLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 0.6, marginTop: 3 },
  pcardVsep: { width: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong },

  pcardActions: { flexDirection: 'row', gap: spacing.sm },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 11, borderRadius: radius.sm,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
    backgroundColor: colors.surfaceTertiary,
  },
  actionBtnPrimary: { borderColor: 'transparent' },
  actionBtnText: { color: colors.onSurface, fontSize: 13, fontWeight: '600' },
  actionBtnGhost: {
    width: 40, height: 40, borderRadius: radius.sm,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: 'rgba(229,72,77,0.3)',
    backgroundColor: 'rgba(229,72,77,0.08)',
  },

  note: {
    flexDirection: 'row', gap: spacing.sm,
    marginTop: spacing.xl, padding: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  noteText: { color: colors.onSurfaceTertiary, fontSize: 11, flex: 1, lineHeight: 16 },

  // Connect modal
  modalBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center', alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  modalSheet: {
    width: '100%', maxWidth: 460,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  modalHeader: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
  modalIcon: {
    width: 42, height: 42, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  modalTitle: { color: colors.onSurface, fontSize: 17, fontWeight: '700', letterSpacing: -0.3 },
  modalSub: { color: colors.onSurfaceTertiary, fontSize: 12, marginTop: 2, lineHeight: 17 },
  modalClose: {
    width: 30, height: 30, borderRadius: 15,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.surfaceTertiary,
  },

  inputLabel: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: '600', marginBottom: 6 },
  inputRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
    paddingHorizontal: spacing.md,
  },
  inputPrefix: { color: colors.onSurfaceSecondary, fontSize: 15, fontWeight: '600', marginRight: 4 },
  input: { flex: 1, color: colors.onSurface, fontSize: 15, paddingVertical: 12 },
  errorText: { color: colors.error, fontSize: 12, marginTop: 6 },

  permissionBox: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: 6,
  },
  permissionTitle: { color: colors.onSurfaceSecondary, fontSize: 11, letterSpacing: 0.6, fontWeight: '700', marginBottom: 4 },
  permRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  permText: { color: colors.onSurface, fontSize: 12, flex: 1 },

  submitBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 13, borderRadius: radius.md,
  },
  submitBtnText: { color: '#fff', fontSize: 14, fontWeight: '700', letterSpacing: -0.2 },
  disclaimer: { color: colors.onSurfaceTertiary, fontSize: 10, textAlign: 'center', lineHeight: 14 },

  progressBlock: {
    alignItems: 'center', justifyContent: 'center',
    paddingVertical: spacing.xl, gap: spacing.md,
  },
  progressTitle: { color: colors.onSurface, fontSize: 16, fontWeight: '700', marginTop: spacing.md },
  progressSub: { color: colors.onSurfaceTertiary, fontSize: 12, textAlign: 'center' },
  successCircle: {
    width: 68, height: 68, borderRadius: 34,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2,
  },

  // Detail modal
  detailBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  detailSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg,
    padding: spacing.lg,
    maxHeight: '82%',
    borderTopWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
  },
  detailHandle: {
    alignSelf: 'center',
    width: 42, height: 4, borderRadius: 2,
    backgroundColor: colors.borderStrong,
    marginBottom: spacing.md,
  },
  detailHeader: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },

  statGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm,
  },
  statCell: {
    flexGrow: 1, minWidth: '30%',
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.sm,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  statValue: { color: colors.onSurface, fontSize: 18, fontWeight: '700', letterSpacing: -0.5 },
  statLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 0.6, marginTop: 3, fontWeight: '600' },

  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.sm,
  },
  cardKicker: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '700' },
  cardBig: { color: colors.onSurface, fontSize: 26, fontWeight: '700', letterSpacing: -1 },
  cardHint: { color: colors.onSurfaceTertiary, fontSize: 11 },

  recentRow: {
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.divider,
  },
  recentPrimary: { color: colors.onSurface, fontSize: 13, fontWeight: '600', lineHeight: 18 },
  recentSecondary: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 3 },
});
