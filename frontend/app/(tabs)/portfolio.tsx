import { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Polyline } from 'react-native-svg';
import { colors, spacing, radius, fmtCurrency, fmtCompact, platformMeta } from '@/src/theme/tokens';
import { api } from '@/src/services/api';
import { track } from '@/src/services/analytics';
import { AddAssetModal } from '@/src/components/AddAssetModal';

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data?.length) return null;
  const w = 64, h = 28;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(' ');
  return (
    <Svg width={w} height={h}>
      <Polyline points={pts} fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function AssetRow({ asset, onPress }: { asset: any; onPress: () => void }) {
  const meta = platformMeta[asset.platform] ?? { label: asset.platform, color: colors.brand, emoji: '◇' };
  return (
    <Pressable style={styles.row} onPress={onPress} testID={`asset-${asset.id}`}>
      <View style={[styles.avatar, { backgroundColor: `${meta.color}22`, borderColor: `${meta.color}55` }]}>
        <Text style={[styles.avatarGlyph, { color: meta.color }]}>{meta.emoji}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.assetName} numberOfLines={1}>{asset.name}</Text>
        <View style={styles.assetMetaRow}>
          <Text style={styles.assetMeta}>{meta.label}</Text>
          <View style={styles.dot} />
          <Text style={styles.assetMeta}>{fmtCompact(asset.followers)} reach</Text>
          <View style={styles.dot} />
          <View style={styles.scorePill}>
            <Text style={styles.scorePillText}>AI {asset.ai_score}</Text>
          </View>
        </View>
      </View>
      <View style={styles.right}>
        <Text style={styles.revenue}>{fmtCurrency(asset.revenue_mtd)}</Text>
        <Sparkline data={asset.trend} color={asset.ai_score >= 75 ? colors.success : colors.brand} />
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceTertiary} />
    </Pressable>
  );
}

export default function Portfolio() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.portfolio()); } catch (e) { console.warn(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!data) {
    return <View style={[styles.root, { alignItems: 'center', justifyContent: 'center' }]}><ActivityIndicator color={colors.brand} /></View>;
  }

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <View>
            <Text style={styles.kicker}>PORTFOLIO</Text>
            <Text style={styles.title}>{data.asset_count} assets</Text>
          </View>
          <Pressable
            style={styles.addBtn}
            onPress={() => setShowAdd(true)}
            testID="add-asset-btn"
          >
            <Ionicons name="add" size={20} color={colors.onBrandPrimary} />
          </Pressable>
        </View>

        <View style={styles.summary}>
          <View style={styles.summaryCol}>
            <Text style={styles.summaryLabel}>Revenue MTD</Text>
            <Text style={styles.summaryValue}>{fmtCurrency(data.total_revenue_mtd)}</Text>
          </View>
          <View style={styles.vsep} />
          <View style={styles.summaryCol}>
            <Text style={styles.summaryLabel}>Profit MTD</Text>
            <Text style={[styles.summaryValue, { color: colors.success }]}>{fmtCurrency(data.total_profit_mtd)}</Text>
          </View>
          <View style={styles.vsep} />
          <View style={styles.summaryCol}>
            <Text style={styles.summaryLabel}>Margin</Text>
            <Text style={styles.summaryValue}>
              {data.total_revenue_mtd ? ((data.total_profit_mtd / data.total_revenue_mtd) * 100).toFixed(0) : '0'}%
            </Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        contentContainerStyle={{ paddingBottom: 120, paddingTop: spacing.md }}
        refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        {data.assets.map((a: any) => (
          <AssetRow
            key={a.id}
            asset={a}
            onPress={() => {
              track('asset_detail_viewed', { asset_id: a.id, platform: a.platform, ai_score: a.ai_score });
              router.push(`/asset/${a.id}`);
            }}
          />
        ))}
      </ScrollView>

      <AddAssetModal
        visible={showAdd}
        onClose={() => setShowAdd(false)}
        onCreated={load}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end',
    paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md,
  },
  kicker: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 1.4, fontWeight: '600' },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },
  addBtn: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.brand,
    alignItems: 'center', justifyContent: 'center',
  },
  summary: {
    flexDirection: 'row',
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    paddingVertical: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  summaryCol: { flex: 1, alignItems: 'center' },
  summaryLabel: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1, fontWeight: '600' },
  summaryValue: { color: colors.onSurface, fontSize: 20, fontWeight: '600', marginTop: spacing.xs, letterSpacing: -0.5 },
  vsep: { width: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong, marginVertical: 6 },

  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
    gap: spacing.md,
  },
  avatar: {
    width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  avatarGlyph: { fontSize: 20, fontWeight: '700' },
  assetName: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 4 },
  assetMeta: { color: colors.onSurfaceTertiary, fontSize: 11, fontWeight: '500' },
  dot: { width: 2, height: 2, borderRadius: 1, backgroundColor: colors.onSurfaceTertiary },
  scorePill: {
    backgroundColor: colors.brandTertiary, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm,
  },
  scorePillText: { color: colors.brand, fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
  right: { alignItems: 'flex-end', gap: 4 },
  revenue: { color: colors.onSurface, fontSize: 14, fontWeight: '600', letterSpacing: -0.2 },
});
