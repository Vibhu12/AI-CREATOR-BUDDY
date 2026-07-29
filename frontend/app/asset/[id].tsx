import { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Polyline, Path, Defs, LinearGradient as SvgGrad, Stop } from 'react-native-svg';
import { colors, spacing, radius, fmtCurrency, fmtCompact, platformMeta } from '@/src/theme/tokens';
import { api } from '@/src/services/api';


function TrendChart({ trend, color }: { trend: number[]; color: string }) {
  const w = 320, h = 100;
  if (!trend?.length) return null;
  const min = Math.min(...trend), max = Math.max(...trend);
  const range = max - min || 1;
  const xs = (i: number) => (i / (trend.length - 1)) * w;
  const ys = (v: number) => h - ((v - min) / range) * (h - 16) - 8;
  const line = trend.map((v, i) => `${i === 0 ? 'M' : 'L'}${xs(i)},${ys(v)}`).join(' ');
  const area = `${line} L${w},${h} L0,${h} Z`;
  return (
    <Svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <Defs>
        <SvgGrad id="atrend" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity="0.32" />
          <Stop offset="1" stopColor={color} stopOpacity="0" />
        </SvgGrad>
      </Defs>
      <Path d={area} fill="url(#atrend)" />
      <Path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}


function ScoreRing({ score, color }: { score: number; color: string }) {
  const size = 88, r = 36, stroke = 8, c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score));
  const dash = (pct / 100) * c;
  return (
    <Svg width={size} height={size}>
      <Polyline points="" />
      <Path
        d={`M ${size / 2} ${size / 2 - r} A ${r} ${r} 0 1 1 ${size / 2 - 0.01} ${size / 2 - r}`}
        fill="none"
        stroke={colors.surfaceTertiary}
        strokeWidth={stroke}
        strokeLinecap="round"
      />
      <Path
        d={`M ${size / 2} ${size / 2 - r} A ${r} ${r} 0 1 1 ${size / 2 - 0.01} ${size / 2 - r}`}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${dash} ${c}`}
      />
    </Svg>
  );
}


export default function AssetDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const r = await api.assetDetail(id);
      setData(r);
    } catch {
      setError('Could not load this asset.');
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (error) {
    return (
      <View style={[styles.root, { alignItems: 'center', justifyContent: 'center', padding: spacing.xl }]}>
        <Ionicons name="alert-circle-outline" size={40} color={colors.error} />
        <Text style={styles.errTitle}>{error}</Text>
        <Pressable onPress={() => router.back()} style={styles.backLinkBtn}>
          <Text style={styles.backLinkText}>Go back</Text>
        </Pressable>
      </View>
    );
  }
  if (!data) {
    return <View style={[styles.root, { alignItems: 'center', justifyContent: 'center' }]}><ActivityIndicator color={colors.brand} /></View>;
  }

  const a = data.asset;
  const meta = platformMeta[a.platform] ?? { label: a.platform, color: colors.brand, emoji: '◇' };
  const b = data.benchmarks;
  const kpis = data.kpis;

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} testID="back-btn">
            <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>{meta.label.toUpperCase()}</Text>
            <Text style={styles.title} numberOfLines={1}>{a.name}</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Hero — AI score + trend */}
        <View style={styles.heroCard}>
          <View style={styles.heroRow}>
            <View style={styles.heroLeft}>
              <View style={[styles.avatar, { backgroundColor: `${meta.color}22`, borderColor: `${meta.color}55` }]}>
                <Text style={[styles.avatarGlyph, { color: meta.color }]}>{meta.emoji}</Text>
              </View>
              <View>
                <Text style={styles.aiScoreValue}>{a.ai_score}</Text>
                <Text style={styles.aiScoreLabel}>AI Score</Text>
              </View>
            </View>
            <View style={styles.heroRight}>
              <ScoreRing score={a.ai_score} color={meta.color} />
              <View style={styles.scoreLabelOverlay}>
                <Text style={[styles.scorePct, { color: meta.color }]}>{a.ai_score}</Text>
                <Text style={styles.scoreSub}>/100</Text>
              </View>
            </View>
          </View>
          <TrendChart trend={a.trend} color={meta.color} />
          <Text style={styles.categoryText}>{a.category}</Text>
        </View>

        {/* KPI grid */}
        <View style={styles.kpiGrid}>
          {kpis.map((k: any, i: number) => (
            <View key={i} style={styles.kpiCell}>
              <Text style={styles.kpiValue}>
                {k.unit === '$' ? `$${fmtCompact(k.value)}` :
                 k.unit === '%' ? `${k.value}%` :
                 k.unit === '/100' ? `${k.value}` :
                 fmtCompact(k.value)}
              </Text>
              <Text style={styles.kpiLabel}>{k.label}</Text>
              {k.unit === 'reach' && (
                <Text style={styles.kpiSublabel}>{k.unit}</Text>
              )}
            </View>
          ))}
        </View>

        {/* Benchmarks */}
        <View style={styles.card}>
          <Text style={styles.cardKicker}>TOP 1% BENCHMARK</Text>
          <View style={styles.bmRow}>
            <View style={styles.bmCol}>
              <Text style={styles.bmLabel}>Your engagement</Text>
              <Text style={styles.bmValue}>{b.your_engagement}%</Text>
              <View style={styles.bmBarBg}>
                <View style={[styles.bmBarFill, { width: `${Math.min(100, (b.your_engagement / 12) * 100)}%`, backgroundColor: colors.brand }]} />
              </View>
            </View>
            <View style={styles.bmCol}>
              <Text style={styles.bmLabel}>Top 1% median</Text>
              <Text style={styles.bmValue}>{b.median_engagement}%</Text>
              <View style={styles.bmBarBg}>
                <View style={[styles.bmBarFill, { width: `${Math.min(100, (b.median_engagement / 12) * 100)}%`, backgroundColor: colors.onSurfaceTertiary }]} />
              </View>
            </View>
          </View>
          <View style={styles.bmSplit}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bmLabel}>Followers gap</Text>
              <Text style={styles.bmValueBig}>{fmtCompact(b.top_1pct_followers - a.followers)}</Text>
              <Text style={styles.bmHint}>to reach top 1%</Text>
            </View>
            <View style={styles.bmVsep} />
            <View style={{ flex: 1 }}>
              <Text style={styles.bmLabel}>Revenue gap</Text>
              <Text style={styles.bmValueBig}>{fmtCurrency(b.top_1pct_revenue - a.revenue_mtd)}</Text>
              <Text style={styles.bmHint}>vs top 1% MTD</Text>
            </View>
          </View>
        </View>

        {/* Recommendations */}
        {data.recommendations?.length > 0 && (
          <View style={{ marginTop: spacing.md }}>
            <Text style={styles.sectionKicker}>AI RECOMMENDATIONS</Text>
            {data.recommendations.map((r: any) => (
              <View key={r.id ?? r.title} style={styles.recCard} testID={`rec-${r.title}`}>
                <View style={styles.recHead}>
                  <View style={[styles.recTag, { backgroundColor: r.priority === 'high' ? 'rgba(229,167,47,0.14)' : 'rgba(138,138,138,0.14)' }]}>
                    <Text style={[styles.recTagText, { color: r.priority === 'high' ? colors.brand : colors.onSurfaceSecondary }]}>
                      {r.priority?.toUpperCase() ?? 'NORMAL'}
                    </Text>
                  </View>
                  <Text style={styles.recRoi}>{r.expected_roi}</Text>
                </View>
                <Text style={styles.recTitle}>{r.title}</Text>
                <Text style={styles.recSummary}>{r.summary}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Recent content */}
        {data.content?.length > 0 && (
          <View style={{ marginTop: spacing.md }}>
            <Text style={styles.sectionKicker}>RECENT CONTENT ({data.content.length})</Text>
            {data.content.slice(0, 6).map((c: any) => (
              <View key={c.id} style={styles.contentRow} testID={`content-${c.id}`}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.contentTitle} numberOfLines={2}>{c.title}</Text>
                  <Text style={styles.contentMeta}>
                    {fmtCompact(c.views)} views · {fmtCompact(c.likes)} likes · CTR {c.ctr}%
                  </Text>
                </View>
                <View style={styles.viralBox}>
                  <Text style={styles.viralScore}>{c.virality}</Text>
                  <Text style={styles.viralLabel}>VIRAL</Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {data.content?.length === 0 && data.recommendations?.length === 0 && (
          <View style={styles.emptyBlock}>
            <Ionicons name="analytics-outline" size={28} color={colors.onSurfaceTertiary} />
            <Text style={styles.emptyText}>
              No content or recommendations yet for this asset.
            </Text>
          </View>
        )}
      </ScrollView>
    </View>
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
  title: { color: colors.onSurface, fontSize: 20, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },

  errTitle: { color: colors.onSurface, fontSize: 16, marginTop: spacing.md, textAlign: 'center' },
  backLinkBtn: {
    marginTop: spacing.lg, paddingHorizontal: spacing.lg, paddingVertical: 10,
    borderRadius: radius.sm, backgroundColor: colors.brand,
  },
  backLinkText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: '600' },

  heroCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.md,
  },
  heroRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  heroLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: {
    width: 48, height: 48, borderRadius: 24,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  avatarGlyph: { fontSize: 22, fontWeight: '700' },
  aiScoreValue: { color: colors.onSurface, fontSize: 30, fontWeight: '700', letterSpacing: -1 },
  aiScoreLabel: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 0.6 },
  heroRight: { width: 88, height: 88, alignItems: 'center', justifyContent: 'center', transform: [{ rotate: '0deg' }] },
  scoreLabelOverlay: { position: 'absolute', alignItems: 'center' },
  scorePct: { fontSize: 22, fontWeight: '700' },
  scoreSub: { color: colors.onSurfaceTertiary, fontSize: 10 },
  categoryText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: '500' },

  kpiGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm,
    marginTop: spacing.md,
  },
  kpiCell: {
    flexGrow: 1, minWidth: '46%',
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.sm, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  kpiValue: { color: colors.onSurface, fontSize: 20, fontWeight: '700', letterSpacing: -0.6 },
  kpiLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 0.8, marginTop: 4, fontWeight: '600' },
  kpiSublabel: { color: colors.onSurfaceTertiary, fontSize: 9, marginTop: 2 },

  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    marginTop: spacing.md, gap: spacing.md,
  },
  cardKicker: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '700' },

  bmRow: { flexDirection: 'row', gap: spacing.md },
  bmCol: { flex: 1, gap: 4 },
  bmLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 0.6, fontWeight: '600' },
  bmValue: { color: colors.onSurface, fontSize: 16, fontWeight: '700' },
  bmValueBig: { color: colors.onSurface, fontSize: 18, fontWeight: '700', letterSpacing: -0.4 },
  bmHint: { color: colors.onSurfaceTertiary, fontSize: 10 },
  bmBarBg: { height: 4, backgroundColor: colors.surfaceTertiary, borderRadius: 2, marginTop: 4, overflow: 'hidden' },
  bmBarFill: { height: '100%', borderRadius: 2 },

  bmSplit: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.sm, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  bmVsep: { width: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong, marginHorizontal: spacing.md },

  sectionKicker: {
    color: colors.onSurfaceSecondary, fontSize: 11, letterSpacing: 1.2, fontWeight: '700',
    marginTop: spacing.md, marginBottom: spacing.sm,
  },

  recCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    marginBottom: spacing.sm, gap: 6,
  },
  recHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  recTag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  recTagText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.6 },
  recRoi: { color: colors.success, fontSize: 12, fontWeight: '700' },
  recTitle: { color: colors.onSurface, fontSize: 14, fontWeight: '600', letterSpacing: -0.2 },
  recSummary: { color: colors.onSurfaceSecondary, fontSize: 12, lineHeight: 17 },

  contentRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  contentTitle: { color: colors.onSurface, fontSize: 13, fontWeight: '500', lineHeight: 18 },
  contentMeta: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 4, letterSpacing: 0.4 },
  viralBox: { alignItems: 'center', minWidth: 40 },
  viralScore: { color: colors.brand, fontSize: 20, fontWeight: '700', letterSpacing: -0.5 },
  viralLabel: { color: colors.onSurfaceTertiary, fontSize: 9, letterSpacing: 0.8, fontWeight: '700' },

  emptyBlock: {
    alignItems: 'center', gap: spacing.sm,
    marginTop: spacing.xxl, padding: spacing.xl,
  },
  emptyText: { color: colors.onSurfaceTertiary, fontSize: 12, textAlign: 'center' },
});
