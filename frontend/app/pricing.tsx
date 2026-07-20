import { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { api } from '@/src/services/api';
import { useAuth } from '@/src/auth/AuthContext';

export default function Pricing() {
  const router = useRouter();
  const { refreshUser, user } = useAuth();
  const [tiers, setTiers] = useState<any[]>([]);
  const [current, setCurrent] = useState<string>(user?.tier ?? 'free');
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [plans, plan] = await Promise.all([api.billingPlans(), api.billingPlan()]);
        setTiers(plans.tiers);
        setCurrent(plan.tier);
      } catch (e) { console.warn(e); }
    })();
  }, []);

  const upgrade = async (tier: string) => {
    if (tier === current) return;
    setBusy(tier);
    try {
      await api.billingUpgrade(tier);
      await refreshUser();
      setCurrent(tier);
    } catch (e) {
      console.warn(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={styles.root}>
      <SafeAreaView edges={['top']} style={{ backgroundColor: colors.surface }}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} testID="back-btn">
            <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
          </Pressable>
          <View>
            <Text style={styles.kicker}>PRICING</Text>
            <Text style={styles.title}>Level up CreatorOS</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <Text style={styles.hero}>Run your creator business like a $10M SaaS.</Text>
        <Text style={styles.heroSub}>
          Cancel anytime. Upgrades are instant. Downgrades take effect next cycle.
        </Text>

        <View style={{ marginTop: spacing.xl, gap: spacing.md }}>
          {tiers.map((t) => {
            const isCurrent = t.id === current;
            const isPopular = t.popular;
            return (
              <View
                key={t.id}
                style={[
                  styles.tierCard,
                  isPopular && styles.tierCardPopular,
                  isCurrent && styles.tierCardCurrent,
                ]}
                testID={`tier-${t.id}`}
              >
                {isPopular && (
                  <View style={styles.popularBadge}>
                    <Ionicons name="star" size={10} color={colors.onBrandPrimary} />
                    <Text style={styles.popularText}>MOST POPULAR</Text>
                  </View>
                )}
                <View style={styles.tierHead}>
                  <Text style={styles.tierName}>{t.name}</Text>
                  {isCurrent && <View style={styles.currentPill}><Text style={styles.currentPillText}>CURRENT</Text></View>}
                </View>
                <Text style={styles.tierTagline}>{t.tagline}</Text>
                <View style={styles.priceRow}>
                  <Text style={styles.priceCurrency}>$</Text>
                  <Text style={styles.price}>{t.price_monthly}</Text>
                  <Text style={styles.priceUnit}>/mo</Text>
                </View>

                <View style={styles.featuresList}>
                  {t.features.map((f: string, i: number) => (
                    <View key={i} style={styles.featureRow}>
                      <Ionicons name="checkmark" size={14} color={colors.brand} />
                      <Text style={styles.featureText}>{f}</Text>
                    </View>
                  ))}
                </View>

                <Pressable
                  onPress={() => upgrade(t.id)}
                  disabled={isCurrent || busy === t.id}
                  style={[
                    styles.tierCta,
                    isCurrent && styles.tierCtaCurrent,
                    isPopular && !isCurrent && styles.tierCtaPopular,
                  ]}
                  testID={`upgrade-${t.id}`}
                >
                  {busy === t.id
                    ? <ActivityIndicator size="small" color={isPopular ? colors.onBrandPrimary : colors.onSurface} />
                    : <Text style={[
                        styles.tierCtaText,
                        isPopular && !isCurrent && { color: colors.onBrandPrimary },
                        isCurrent && { color: colors.onSurfaceSecondary },
                      ]}>
                        {isCurrent ? 'Current plan' : t.cta}
                      </Text>
                  }
                </Pressable>
              </View>
            );
          })}
        </View>

        <View style={styles.note}>
          <Ionicons name="information-circle-outline" size={14} color={colors.onSurfaceTertiary} />
          <Text style={styles.noteText}>
            Real Stripe Checkout will replace this mock upgrade once a valid Stripe key is configured.
          </Text>
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

  hero: { color: colors.onSurface, fontSize: 24, fontWeight: '700', letterSpacing: -0.8, lineHeight: 30 },
  heroSub: { color: colors.onSurfaceSecondary, fontSize: 13, marginTop: spacing.sm, lineHeight: 18 },

  tierCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.sm,
  },
  tierCardPopular: { borderColor: colors.brand, borderWidth: 1 },
  tierCardCurrent: { backgroundColor: colors.brandTertiary, borderColor: colors.brand, borderWidth: 1 },
  popularBadge: {
    position: 'absolute', top: -10, right: 16,
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: colors.brand,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill,
  },
  popularText: { color: colors.onBrandPrimary, fontSize: 9, fontWeight: '700', letterSpacing: 0.6 },

  tierHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  tierName: { color: colors.onSurface, fontSize: 20, fontWeight: '700', letterSpacing: -0.4 },
  currentPill: { backgroundColor: colors.brand, paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill },
  currentPillText: { color: colors.onBrandPrimary, fontSize: 9, fontWeight: '700', letterSpacing: 0.6 },
  tierTagline: { color: colors.onSurfaceSecondary, fontSize: 12 },

  priceRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: spacing.sm },
  priceCurrency: { color: colors.onSurface, fontSize: 18, fontWeight: '500' },
  price: { color: colors.onSurface, fontSize: 40, fontWeight: '700', letterSpacing: -1.5 },
  priceUnit: { color: colors.onSurfaceTertiary, fontSize: 13, marginLeft: 4 },

  featuresList: { marginTop: spacing.md, gap: spacing.sm },
  featureRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  featureText: { color: colors.onSurface, fontSize: 13, flex: 1 },

  tierCta: {
    marginTop: spacing.lg,
    paddingVertical: 12,
    borderRadius: radius.md,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    backgroundColor: colors.surfaceTertiary,
  },
  tierCtaPopular: { backgroundColor: colors.brand, borderColor: colors.brand },
  tierCtaCurrent: { backgroundColor: 'transparent', borderColor: colors.borderStrong },
  tierCtaText: { color: colors.onSurface, fontSize: 14, fontWeight: '700' },

  note: {
    flexDirection: 'row', gap: spacing.sm,
    marginTop: spacing.xl, padding: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  noteText: { color: colors.onSurfaceTertiary, fontSize: 11, flex: 1, lineHeight: 16 },
});
