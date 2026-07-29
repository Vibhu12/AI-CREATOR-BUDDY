import { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Path, Defs, LinearGradient as SvgGrad, Stop } from 'react-native-svg';
import { colors, spacing, radius, fmtCurrency, platformMeta } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const RANGES = [
  { key: '1W', days: 7 },
  { key: '1M', days: 30 },
  { key: '3M', days: 30 }, // 30 days seeded — 3M is visual placeholder
  { key: '90d fcst', days: 90, forecast: true },
];

function LineChart({ series, range, isForecast }: { series: any[]; range: number; isForecast?: boolean }) {
  const w = 320, h = 160;
  const data = series.slice(-range);
  if (!data.length) return null;
  const revs = data.map((d: any) => d.revenue);
  const max = Math.max(...revs);
  const min = Math.min(...revs);
  const range_y = max - min || 1;
  const xs = (i: number) => (i / (data.length - 1)) * w;
  const ys = (v: number) => h - ((v - min) / range_y) * (h - 20) - 10;

  const linePts = data.map((d: any, i: number) => `${i === 0 ? 'M' : 'L'}${xs(i)},${ys(d.revenue)}`).join(' ');
  const areaPts = `${linePts} L${w},${h} L0,${h} Z`;
  const strokeColor = isForecast ? colors.brandSecondary : colors.brand;

  return (
    <Svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <Defs>
        <SvgGrad id="area" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={strokeColor} stopOpacity="0.35" />
          <Stop offset="1" stopColor={strokeColor} stopOpacity="0" />
        </SvgGrad>
      </Defs>
      <Path d={areaPts} fill="url(#area)" />
      <Path
        d={linePts}
        fill="none"
        stroke={strokeColor}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={isForecast ? '4 4' : undefined}
      />
    </Svg>
  );
}


export default function Finance() {
  const [data, setData] = useState<any>(null);
  const [range, setRange] = useState<{ days: number; forecast?: boolean }>({ days: 30 });
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.finance()); } catch (e) { console.warn(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!data) {
    return <View style={[styles.root, { alignItems: 'center', justifyContent: 'center' }]}><ActivityIndicator color={colors.brand} /></View>;
  }

  const chartSeries = range.forecast ? data.projection : data.series;

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

      <ScrollView
        contentContainerStyle={{ paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        <View style={styles.chartCard} testID="finance-chart">
          <LineChart series={chartSeries} range={range.days} isForecast={range.forecast} />
          <View style={styles.rangeRow}>
            {RANGES.map(r => {
              const active = range.days === r.days && !!range.forecast === !!r.forecast;
              return (
                <Pressable
                  key={r.key}
                  onPress={() => setRange({ days: r.days, forecast: r.forecast })}
                  style={[styles.rangeBtn, active && styles.rangeBtnActive]}
                  testID={`range-${r.key.replace(/\s+/g, '-')}`}
                >
                  <Text style={[styles.rangeText, active && styles.rangeTextActive]}>{r.key}</Text>
                </Pressable>
              );
            })}
          </View>
          {range.forecast && (
            <Text style={styles.forecastHint}>
              <Ionicons name="sparkles" size={11} color={colors.brandSecondary} /> Forward projection · dashed = forecast
            </Text>
          )}
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
            <Text style={styles.statLabel}>90d forecast</Text>
            <Text style={styles.statValue}>{fmtCurrency(data.summary.forecast_90d ?? data.summary.forecast_60d * 1.4)}</Text>
          </View>
        </View>

        {/* Revenue mix by asset */}
        {data.by_asset?.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Revenue mix</Text>
              <Text style={styles.sectionMeta}>Top {data.by_asset.length} assets</Text>
            </View>
            <View style={styles.mixCard}>
              {/* Stacked bar */}
              <View style={styles.stackBar}>
                {data.by_asset.slice(0, 6).map((a: any, i: number) => {
                  const meta = platformMeta[a.platform] ?? { color: colors.brand };
                  return (
                    <View
                      key={a.id ?? i}
                      style={{ flex: a.share, backgroundColor: meta.color, height: '100%' }}
                    />
                  );
                })}
              </View>
              {data.by_asset.slice(0, 6).map((a: any) => {
                const meta = platformMeta[a.platform] ?? { color: colors.brand, label: a.platform };
                return (
                  <View key={a.id} style={styles.mixRow} testID={`mix-${a.id}`}>
                    <View style={[styles.mixDot, { backgroundColor: meta.color }]} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.mixName} numberOfLines={1}>{a.name}</Text>
                      <Text style={styles.mixMeta}>{meta.label} · {a.share}%</Text>
                    </View>
                    <Text style={styles.mixValue}>{fmtCurrency(a.revenue_mtd)}</Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* Expense categories */}
        {data.expense_categories?.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Expense breakdown</Text>
            <View style={styles.expenseCard}>
              {data.expense_categories.map((e: any) => (
                <View key={e.label} style={styles.expenseRow} testID={`expense-${e.label}`}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.expenseLabel}>{e.label}</Text>
                    <View style={styles.expenseBarBg}>
                      <View style={[styles.expenseBarFill, { width: `${e.share}%` }]} />
                    </View>
                  </View>
                  <Text style={styles.expenseAmount}>{fmtCurrency(e.amount)}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

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
  forecastHint: { color: colors.onSurfaceTertiary, fontSize: 10, textAlign: 'center', marginTop: spacing.sm },

  splitRow: { flexDirection: 'row', gap: spacing.md, marginHorizontal: spacing.lg, marginTop: spacing.md },
  statCard: {
    flex: 1, backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  statLabel: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1, fontWeight: '600' },
  statValue: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: spacing.sm, letterSpacing: -0.5 },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.xl },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: spacing.md },
  sectionTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600', marginBottom: spacing.md },
  sectionMeta: { color: colors.onSurfaceTertiary, fontSize: 11 },

  mixCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.sm,
  },
  stackBar: {
    height: 10, borderRadius: 5, overflow: 'hidden',
    flexDirection: 'row',
    backgroundColor: colors.surfaceTertiary,
    marginBottom: spacing.sm,
  },
  mixRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  mixDot: { width: 8, height: 8, borderRadius: 4 },
  mixName: { color: colors.onSurface, fontSize: 13, fontWeight: '500' },
  mixMeta: { color: colors.onSurfaceTertiary, fontSize: 10, marginTop: 1 },
  mixValue: { color: colors.onSurface, fontSize: 13, fontWeight: '600', letterSpacing: -0.2 },

  expenseCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.md,
  },
  expenseRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  expenseLabel: { color: colors.onSurface, fontSize: 12, fontWeight: '500' },
  expenseBarBg: { height: 4, backgroundColor: colors.surfaceTertiary, borderRadius: 2, marginTop: 6, overflow: 'hidden' },
  expenseBarFill: { height: '100%', backgroundColor: colors.error, borderRadius: 2 },
  expenseAmount: { color: colors.onSurface, fontSize: 13, fontWeight: '600', letterSpacing: -0.2 },

  txRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  txIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  txLabel: { color: colors.onSurface, fontSize: 13, flex: 1 },
  txAmount: { fontSize: 14, fontWeight: '600', letterSpacing: -0.2 },
});
