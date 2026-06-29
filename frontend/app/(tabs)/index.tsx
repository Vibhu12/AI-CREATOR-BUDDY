import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, Defs, LinearGradient as SvgGrad, Stop } from 'react-native-svg';
import { colors, spacing, radius, fmtCurrency, fmtCompact, fmtPercent } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

type DashboardData = any;

function HeroRing({ score }: { score: number }) {
  const size = 200;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  return (
    <Svg width={size} height={size}>
      <Defs>
        <SvgGrad id="ring" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={colors.brandSecondary} />
          <Stop offset="1" stopColor={colors.brand} />
        </SvgGrad>
      </Defs>
      <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.surfaceTertiary} strokeWidth={stroke} fill="none" />
      <Circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke="url(#ring)"
        strokeWidth={stroke}
        strokeLinecap="round"
        fill="none"
        strokeDasharray={`${c} ${c}`}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </Svg>
  );
}

function MetricCard({ label, value, delta, format }: any) {
  const positive = delta >= 0;
  const display =
    format === 'currency' ? fmtCurrency(value) :
    format === 'percent'  ? fmtPercent(value) :
    format === 'compact'  ? fmtCompact(value) :
    String(value);
  return (
    <View style={styles.metric} testID={`metric-${label}`}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{display}</Text>
      <View style={styles.deltaRow}>
        <Ionicons
          name={positive ? 'arrow-up' : 'arrow-down'}
          size={11}
          color={positive ? colors.success : colors.error}
        />
        <Text style={[styles.deltaText, { color: positive ? colors.success : colors.error }]}>
          {Math.abs(delta).toFixed(1)}%
        </Text>
      </View>
    </View>
  );
}

const PRIORITY_COLOR: Record<string, string> = {
  high: colors.brand,
  medium: '#7FB3FF',
  low: colors.onSurfaceSecondary,
};

function RecCard({ rec }: { rec: any }) {
  return (
    <View style={styles.recCard} testID={`rec-${rec.id}`}>
      <View style={styles.recHeader}>
        <View style={[styles.priorityDot, { backgroundColor: PRIORITY_COLOR[rec.priority] }]} />
        <Text style={styles.priorityLabel}>{String(rec.priority).toUpperCase()} · {rec.category}</Text>
      </View>
      <Text style={styles.recTitle}>{rec.title}</Text>
      <Text style={styles.recSummary} numberOfLines={3}>{rec.summary}</Text>
      <View style={styles.recFooter}>
        <View style={styles.recPill}>
          <Ionicons name="trending-up" size={12} color={colors.brand} />
          <Text style={styles.recPillText}>{rec.expected_roi}</Text>
        </View>
        <Text style={styles.recConfidence}>{rec.confidence}% confidence</Text>
      </View>
    </View>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.dashboard()); } catch (e) { console.warn(e); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  if (!data) {
    return (
      <View style={[styles.root, styles.center]}>
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.headerBar}>
          <View>
            <Text style={styles.headerKicker}>OVERVIEW</Text>
            <Text style={styles.headerTitle} testID="dashboard-greeting">{data.greeting}</Text>
          </View>
          <Pressable style={styles.notifBtn} testID="notifications-btn">
            <Ionicons name="notifications-outline" size={20} color={colors.onSurface} />
            <View style={styles.notifDot} />
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView
        contentContainerStyle={{ paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Hero AI Score */}
        <View style={styles.hero} testID="hero-score">
          <LinearGradient
            colors={['#1C1408', '#0A0805', colors.surface]}
            style={StyleSheet.absoluteFill}
          />
          <View style={styles.heroInner}>
            <View style={styles.ringWrap}>
              <HeroRing score={data.hero.score} />
              <View style={styles.ringCenter}>
                <Text style={styles.ringScore}>{data.hero.score}</Text>
                <Text style={styles.ringLabel}>{data.hero.label}</Text>
              </View>
            </View>
            <Text style={styles.heroSubtitle}>{data.subtitle}</Text>
            <View style={styles.heroDelta}>
              <Ionicons name="trending-up" size={13} color={colors.success} />
              <Text style={styles.heroDeltaText}>{data.hero.delta}</Text>
            </View>

            <View style={styles.breakdownRow}>
              {data.hero.breakdown.map((b: any) => (
                <View key={b.label} style={styles.breakdownItem}>
                  <Text style={styles.breakdownValue}>{b.value}</Text>
                  <Text style={styles.breakdownLabel}>{b.label}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* Alerts */}
        {data.alerts?.length > 0 && (
          <View style={styles.section}>
            {data.alerts.map((a: any, i: number) => (
              <View key={i} style={styles.alertRow} testID={`alert-${i}`}>
                <View style={[styles.alertIcon, { backgroundColor: a.kind === 'viral' ? '#3A2B0E' : '#0D2A1A' }]}>
                  <Ionicons
                    name={a.kind === 'viral' ? 'flame' : 'compass'}
                    size={14}
                    color={a.kind === 'viral' ? colors.brand : colors.success}
                  />
                </View>
                <Text style={styles.alertText} numberOfLines={2}>{a.text}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Metric grid */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>This month</Text>
          <View style={styles.metricGrid}>
            {data.metrics.map((m: any) => (
              <MetricCard key={m.key} {...m} />
            ))}
          </View>
        </View>

        {/* Recommendations carousel */}
        <View style={[styles.section, { paddingHorizontal: 0 }]}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>AI Recommendations</Text>
            <Text style={styles.sectionMeta}>{data.recommendations.length} active</Text>
          </View>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingHorizontal: spacing.lg, gap: spacing.md }}
          >
            {data.recommendations.map((r: any) => <RecCard key={r.id} rec={r} />)}
          </ScrollView>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: 'center', justifyContent: 'center' },
  headerBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  headerKicker: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600' },
  headerTitle: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },
  notifBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: colors.surfaceSecondary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  notifDot: {
    position: 'absolute', top: 9, right: 11,
    width: 8, height: 8, borderRadius: 4, backgroundColor: colors.brand,
    borderWidth: 2, borderColor: colors.surface,
  },

  hero: {
    marginTop: spacing.sm,
    marginHorizontal: spacing.lg,
    borderRadius: radius.lg,
    overflow: 'hidden',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.borderStrong,
  },
  heroInner: { padding: spacing.xl, alignItems: 'center' },
  ringWrap: { alignItems: 'center', justifyContent: 'center' },
  ringCenter: { position: 'absolute', alignItems: 'center' },
  ringScore: { color: colors.onSurface, fontSize: 64, fontWeight: '700', letterSpacing: -2 },
  ringLabel: { color: colors.onSurfaceSecondary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600', marginTop: -4 },
  heroSubtitle: { color: colors.onSurface, fontSize: 15, marginTop: spacing.lg, textAlign: 'center', maxWidth: 280 },
  heroDelta: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(69,201,122,0.10)',
    borderRadius: radius.pill,
    paddingHorizontal: 10, paddingVertical: 5, marginTop: spacing.md,
  },
  heroDeltaText: { color: colors.success, fontSize: 12, fontWeight: '600' },
  breakdownRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    marginTop: spacing.xl,
    paddingTop: spacing.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderStrong,
  },
  breakdownItem: { alignItems: 'center', flex: 1 },
  breakdownValue: { color: colors.onSurface, fontSize: 22, fontWeight: '600', letterSpacing: -0.5 },
  breakdownLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, marginTop: 2, fontWeight: '600' },

  section: { marginTop: spacing.xl, paddingHorizontal: spacing.lg },
  sectionHeader: {
    flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
  },
  sectionTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },
  sectionMeta: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1, fontWeight: '600', marginBottom: spacing.md },

  alertRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md, paddingVertical: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  alertIcon: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  alertText: { color: colors.onSurface, fontSize: 13, flex: 1, lineHeight: 18 },

  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  metric: {
    width: '47.8%',
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  metricLabel: { color: colors.onSurfaceSecondary, fontSize: 11, letterSpacing: 1, fontWeight: '600' },
  metricValue: { color: colors.onSurface, fontSize: 28, fontWeight: '600', marginTop: spacing.sm, letterSpacing: -0.8 },
  deltaRow: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 4 },
  deltaText: { fontSize: 12, fontWeight: '600' },

  recCard: {
    width: 280,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  recHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  priorityDot: { width: 8, height: 8, borderRadius: 4 },
  priorityLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '700' },
  recTitle: { color: colors.onSurface, fontSize: 16, fontWeight: '600', marginTop: spacing.md, letterSpacing: -0.2 },
  recSummary: { color: colors.onSurfaceSecondary, fontSize: 13, marginTop: spacing.sm, lineHeight: 19 },
  recFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.lg },
  recPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: colors.brandTertiary,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill,
  },
  recPillText: { color: colors.brand, fontSize: 11, fontWeight: '700' },
  recConfidence: { color: colors.onSurfaceTertiary, fontSize: 11, fontWeight: '500' },
});
