import { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Path, Defs, LinearGradient as SvgGrad, Stop } from 'react-native-svg';
import { colors, spacing, radius, fmtCurrency } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const RANGES = [
  { key: '1W', days: 7 },
  { key: '1M', days: 30 },
  { key: '3M', days: 30 }, // we have 30 days seeded; visual only
];

function LineChart({ series, range }: { series: any[]; range: number }) {
  const w = 320, h = 160;
  const data = series.slice(-range);
  if (!data.length) return null;
  const max = Math.max(...data.map((d: any) => d.revenue));
  const min = Math.min(...data.map((d: any) => d.revenue));
  const range_y = max - min || 1;
  const xs = (i: number) => (i / (data.length - 1)) * w;
  const ys = (v: number) => h - ((v - min) / range_y) * (h - 20) - 10;

  const linePts = data.map((d: any, i: number) => `${i === 0 ? 'M' : 'L'}${xs(i)},${ys(d.revenue)}`).join(' ');
  const areaPts = `${linePts} L${w},${h} L0,${h} Z`;

  return (
    <Svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <Defs>
        <SvgGrad id="area" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={colors.brand} stopOpacity="0.35" />
          <Stop offset="1" stopColor={colors.brand} stopOpacity="0" />
        </SvgGrad>
      </Defs>
      <Path d={areaPts} fill="url(#area)" />
      <Path d={linePts} fill="none" stroke={colors.brand} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export default function Finance() {
  const [data, setData] = useState<any>(null);
  const [range, setRange] = useState(30);

  const load = useCallback(async () => {
    try { setData(await api.finance()); } catch (e) { console.warn(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!data) {
    return <View style={[styles.root, { alignItems: 'center', justifyContent: 'center' }]}><ActivityIndicator color={colors.brand} /></View>;
  }

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Text style={styles.kicker}>FINANCIAL INTELLIGENCE</Text>
          <Text style={styles.title}>{fmtCurrency(data.summary.revenue_30d)}</Text>
          <View style={styles.deltaRow}>
            <Ionicons name="trending-up" size={13} color={colors.success} />
            <Text style={styles.delta}>+{data.summary.margin}% margin · 30 days</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <View style={styles.chartCard} testID="finance-chart">
          <LineChart series={data.series} range={range} />
          <View style={styles.rangeRow}>
            {RANGES.map(r => (
              <Pressable
                key={r.key}
                onPress={() => setRange(r.days)}
                style={[styles.rangeBtn, range === r.days && styles.rangeBtnActive]}
                testID={`range-${r.key}`}
              >
                <Text style={[styles.rangeText, range === r.days && styles.rangeTextActive]}>{r.key}</Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.splitRow}>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>Profit 30d</Text>
            <Text style={[styles.statValue, { color: colors.success }]}>{fmtCurrency(data.summary.profit_30d)}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>Expense 30d</Text>
            <Text style={[styles.statValue, { color: colors.error }]}>{fmtCurrency(data.summary.expense_30d)}</Text>
          </View>
        </View>

        <View style={styles.splitRow}>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>60d forecast</Text>
            <Text style={styles.statValue}>{fmtCurrency(data.summary.forecast_60d)}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>Runway</Text>
            <Text style={styles.statValue}>{data.summary.runway_months} mo</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent transactions</Text>
          {data.transactions.map((t: any) => (
            <View key={t.id} style={styles.txRow} testID={`tx-${t.id}`}>
              <View style={[styles.txIcon, { backgroundColor: t.kind === 'in' ? 'rgba(69,201,122,0.12)' : 'rgba(229,72,77,0.12)' }]}>
                <Ionicons
                  name={t.kind === 'in' ? 'arrow-down' : 'arrow-up'}
                  size={14}
                  color={t.kind === 'in' ? colors.success : colors.error}
                />
              </View>
              <Text style={styles.txLabel} numberOfLines={1}>{t.label}</Text>
              <Text style={[styles.txAmount, { color: t.kind === 'in' ? colors.success : colors.error }]}>
                {t.kind === 'in' ? '+' : ''}{fmtCurrency(Math.abs(t.amount))}
              </Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.lg },
  kicker: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600' },
  title: { color: colors.onSurface, fontSize: 42, fontWeight: '700', marginTop: 4, letterSpacing: -1.2 },
  deltaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  delta: { color: colors.success, fontSize: 12, fontWeight: '600' },

  chartCard: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    padding: spacing.md,
  },
  rangeRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md, justifyContent: 'center' },
  rangeBtn: { paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: 'transparent' },
  rangeBtnActive: { backgroundColor: colors.brandTertiary },
  rangeText: { color: colors.onSurfaceTertiary, fontSize: 12, fontWeight: '600' },
  rangeTextActive: { color: colors.brand },

  splitRow: { flexDirection: 'row', gap: spacing.md, marginHorizontal: spacing.lg, marginTop: spacing.md },
  statCard: {
    flex: 1, backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  statLabel: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1, fontWeight: '600' },
  statValue: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: spacing.sm, letterSpacing: -0.5 },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.xl },
  sectionTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },
  txRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  txIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  txLabel: { color: colors.onSurface, fontSize: 13, flex: 1 },
  txAmount: { fontSize: 14, fontWeight: '600', letterSpacing: -0.2 },
});
