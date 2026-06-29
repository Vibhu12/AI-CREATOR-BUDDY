import { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Polygon, Line, Circle, Text as SvgText } from 'react-native-svg';
import { colors, spacing, radius, fmtCompact } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

function RadarChart({ dimensions }: { dimensions: any[] }) {
  const size = 280;
  const cx = size / 2, cy = size / 2;
  const radius_ = size / 2 - 30;
  const n = dimensions.length;
  if (!n) return null;
  const angle = (i: number) => (-Math.PI / 2) + (i * 2 * Math.PI) / n;
  const point = (i: number, v: number) => {
    const a = angle(i);
    const r = (v / 100) * radius_;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  };
  const ringPolygon = (r: number) =>
    Array.from({ length: n }, (_, i) => {
      const a = angle(i);
      return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
    }).join(' ');
    Array.from({ length: n }, (_, i) => {
      const a = angle(i);
      return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
    }).join(' ');
  const dataPoly = (key: 'you' | 'top_1' | 'industry_avg') =>
    dimensions.map((d, i) => point(i, d[key]).join(',')).join(' ');

  return (
    <Svg width={size} height={size}>
      {[0.25, 0.5, 0.75, 1].map((f, i) => (
        <Polygon
          key={i}
          points={ringPolygon(radius_ * f)}
          fill="none"
          stroke={colors.surfaceTertiary}
          strokeWidth={0.6}
        />
      ))}
      {dimensions.map((_, i) => {
        const [x, y] = point(i, 100);
        return <Line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={colors.surfaceTertiary} strokeWidth={0.6} />;
      })}
      {/* Industry avg */}
      <Polygon
        points={dataPoly('industry_avg')}
        fill={colors.onSurfaceTertiary}
        fillOpacity={0.08}
        stroke={colors.onSurfaceTertiary}
        strokeWidth={1}
        strokeDasharray="3 3"
      />
      {/* Top 1% */}
      <Polygon
        points={dataPoly('top_1')}
        fill={colors.brand}
        fillOpacity={0.10}
        stroke={colors.brand}
        strokeWidth={1.4}
      />
      {/* You */}
      <Polygon
        points={dataPoly('you')}
        fill={colors.success}
        fillOpacity={0.18}
        stroke={colors.success}
        strokeWidth={2}
      />
      {dimensions.map((d, i) => {
        // push label slightly outward
        const a = angle(i);
        const lx = cx + Math.cos(a) * (radius_ + 16);
        const ly = cy + Math.sin(a) * (radius_ + 16);
        return (
          <SvgText
            key={i}
            x={lx}
            y={ly + 3}
            fontSize="10"
            fill={colors.onSurfaceSecondary}
            textAnchor="middle"
            fontWeight="600"
          >
            {d.label.toUpperCase()}
          </SvgText>
        );
      })}
      {/* dots on your line */}
      {dimensions.map((d, i) => {
        const [x, y] = point(i, d.you);
        return <Circle key={`u-${i}`} cx={x} cy={y} r={3} fill={colors.success} />;
      })}
    </Svg>
  );
}

function GapBar({ item }: { item: any }) {
  const youW = (item.you / item.top_1) * 100;
  const format = item.key.includes('rate') ? (n: number) => `${n.toFixed(1)}%` : fmtCompact;
  return (
    <View style={styles.gapRow} testID={`gap-${item.key}`}>
      <View style={styles.gapHead}>
        <Text style={styles.gapLabel}>{item.label}</Text>
        <Text style={styles.gapPct}>-{item.gap_pct.toFixed(0)}%</Text>
      </View>
      <View style={styles.gapBarTrack}>
        <View style={[styles.gapBarFill, { width: `${Math.min(100, youW)}%` }]} />
      </View>
      <View style={styles.gapStats}>
        <Text style={styles.gapStat}>You {format(item.you)}</Text>
        <Text style={styles.gapStatRight}>Top 1% {format(item.top_1)}</Text>
      </View>
    </View>
  );
}

export default function Competitors() {
  const router = useRouter();
  const [radar, setRadar] = useState<any>(null);
  const [gaps, setGaps] = useState<any>(null);

  useEffect(() => {
    Promise.all([api.competitorsRadar(), api.competitorsGaps()])
      .then(([r, g]) => { setRadar(r); setGaps(g); })
      .catch(() => {});
  }, []);

  if (!radar || !gaps) {
    return <View style={[styles.root, { alignItems: 'center', justifyContent: 'center' }]}><ActivityIndicator color={colors.brand} /></View>;
  }

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} testID="back-btn">
            <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
          </Pressable>
          <View>
            <Text style={styles.kicker}>BENCHMARK</Text>
            <Text style={styles.title}>You vs Top 1%</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <View style={styles.radarCard}>
          <View style={{ alignItems: 'center' }}>
            <RadarChart dimensions={radar.dimensions} />
          </View>
          <View style={styles.legendRow}>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: colors.success }]} />
              <Text style={styles.legendText}>You</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: colors.brand }]} />
              <Text style={styles.legendText}>Top 1%</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: colors.onSurfaceTertiary }]} />
              <Text style={styles.legendText}>Industry avg</Text>
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Biggest gaps</Text>
          <Text style={styles.sectionSub}>Where you trail the top 1%, ranked by upside.</Text>
          <View style={{ marginTop: spacing.md }}>
            {gaps.items.slice(0, 6).map((g: any) => <GapBar key={g.key} item={g} />)}
          </View>
        </View>
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

  radarCard: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  legendRow: { flexDirection: 'row', justifyContent: 'center', gap: spacing.lg, marginTop: spacing.md },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { color: colors.onSurfaceSecondary, fontSize: 11, fontWeight: '600' },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.xl },
  sectionTitle: { color: colors.onSurface, fontSize: 13, letterSpacing: 1.2, fontWeight: '600' },
  sectionSub: { color: colors.onSurfaceTertiary, fontSize: 12, marginTop: 4 },

  gapRow: { marginBottom: spacing.lg },
  gapHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm },
  gapLabel: { color: colors.onSurface, fontSize: 13, fontWeight: '600' },
  gapPct: { color: colors.error, fontSize: 13, fontWeight: '700' },
  gapBarTrack: { height: 6, backgroundColor: colors.surfaceTertiary, borderRadius: 3, overflow: 'hidden' },
  gapBarFill: { height: '100%', backgroundColor: colors.brand },
  gapStats: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  gapStat: { color: colors.onSurfaceSecondary, fontSize: 11 },
  gapStatRight: { color: colors.brand, fontSize: 11, fontWeight: '600' },
});
