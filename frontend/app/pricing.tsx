import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { api } from '@/src/services/api';
import { useAuth } from '@/src/auth/AuthContext';
import { track } from '@/src/services/analytics';

type CheckoutPhase = 'idle' | 'creating' | 'method' | 'processing' | 'success' | 'error';

export default function Pricing() {
  const router = useRouter();
  const { refreshUser, user } = useAuth();
  const [tiers, setTiers] = useState<any[]>([]);
  const [current, setCurrent] = useState<string>(user?.tier ?? 'free');
  const [paypalLive, setPaypalLive] = useState<boolean>(false);
  const [paypalMode, setPaypalMode] = useState<string | null>(null);

  // Checkout state
  const [checkoutTier, setCheckoutTier] = useState<any>(null);
  const [phase, setPhase] = useState<CheckoutPhase>('idle');
  const [session, setSession] = useState<any>(null);
  const [provider, setProvider] = useState<'stripe' | 'paypal'>('stripe');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [plans, plan, pp] = await Promise.all([
          api.billingPlans(), api.billingPlan(), api.paypalConfig(),
        ]);
        setTiers(plans.tiers);
        setCurrent(plan.tier);
        setPaypalLive(!!pp.configured);
        setPaypalMode(pp.mode);
      } catch (e) { console.warn(e); }
    })();
  }, []);

  const startCheckout = (tier: any) => {
    if (tier.id === current) return;
    if (tier.price_monthly === 0) return;
    setCheckoutTier(tier);
    setProvider('stripe');
    setErrorMsg(null);
    setPhase('method');
    track('checkout_started', { tier: tier.id, price: tier.price_monthly });
  };

  const runStripeCheckout = async () => {
    // Existing mock Stripe flow — unchanged
    setPhase('creating');
    track('checkout_method_selected', { tier: checkoutTier.id, provider: 'stripe' });
    const t0 = Date.now();
    try {
      const s = await api.billingCheckout(checkoutTier.id, 'stripe');
      setSession(s);
      setPhase('processing');
      await new Promise(r => setTimeout(r, 1400));
      const res = await api.billingConfirm(s.session_id);
      await refreshUser();
      setCurrent(res.tier);
      setPhase('success');
      track('checkout_completed', { tier: res.tier, provider: 'stripe', real: false, ms: Date.now() - t0 });
      setTimeout(() => { setPhase('idle'); setCheckoutTier(null); setSession(null); }, 1600);
    } catch (e: any) {
      setErrorMsg(e?.message ?? 'Checkout failed');
      setPhase('error');
      track('checkout_failed', { tier: checkoutTier.id, provider: 'stripe', reason: 'exception' });
    }
  };

  const runPayPalCheckout = async () => {
    // Real PayPal flow: create order → open approval URL → capture on return
    setPhase('creating');
    track('checkout_method_selected', { tier: checkoutTier.id, provider: 'paypal', live: paypalLive });
    const t0 = Date.now();
    try {
      const returnUrl = Linking.createURL('paypal/return');
      const cancelUrl = Linking.createURL('paypal/cancel');
      const s = await api.paypalCreateOrder(checkoutTier.id, returnUrl, cancelUrl);
      setSession(s);

      // If backend returned a real approval_url, open the PayPal hosted page
      if (s.approval_url && !s.mocked) {
        setPhase('processing');
        const result = await WebBrowser.openAuthSessionAsync(s.approval_url, returnUrl);
        if (result.type !== 'success' || !result.url) {
          setErrorMsg('Payment was cancelled or dismissed.');
          setPhase('error');
          track('checkout_cancelled', { tier: checkoutTier.id, provider: 'paypal' });
          return;
        }
        // Extract order id — PayPal appends ?token=<order_id>&PayerID=...
        const cb = new URL(result.url);
        const orderId = cb.searchParams.get('token') || s.order_id;
        const capture = await api.paypalCapture(orderId);
        await refreshUser();
        setCurrent(capture.tier);
        setPhase('success');
        track('checkout_completed', { tier: capture.tier, provider: 'paypal', real: true, ms: Date.now() - t0 });
        setTimeout(() => { setPhase('idle'); setCheckoutTier(null); setSession(null); }, 1600);
      } else {
        // Fallback: mocked PayPal path (no keys) — simulate + capture
        setPhase('processing');
        await new Promise(r => setTimeout(r, 1400));
        const capture = await api.paypalCapture(s.order_id);
        await refreshUser();
        setCurrent(capture.tier);
        setPhase('success');
        track('checkout_completed', { tier: capture.tier, provider: 'paypal', real: false, ms: Date.now() - t0 });
        setTimeout(() => { setPhase('idle'); setCheckoutTier(null); setSession(null); }, 1600);
      }
    } catch (e: any) {
      setErrorMsg(e?.message ?? 'PayPal checkout failed');
      setPhase('error');
      track('checkout_failed', { tier: checkoutTier.id, provider: 'paypal', reason: 'exception' });
    }
  };

  const confirmCheckout = () => {
    setErrorMsg(null);
    if (provider === 'paypal') runPayPalCheckout();
    else runStripeCheckout();
  };

  const closeCheckout = () => {
    if (phase === 'processing' || phase === 'creating') return; // block cancel mid-flight
    setPhase('idle');
    setCheckoutTier(null);
    setSession(null);
    setErrorMsg(null);
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
                  onPress={() => startCheckout(t)}
                  disabled={isCurrent}
                  style={[
                    styles.tierCta,
                    isCurrent && styles.tierCtaCurrent,
                    isPopular && !isCurrent && styles.tierCtaPopular,
                  ]}
                  testID={`upgrade-${t.id}`}
                >
                  <Text style={[
                    styles.tierCtaText,
                    isPopular && !isCurrent && { color: colors.onBrandPrimary },
                    isCurrent && { color: colors.onSurfaceSecondary },
                  ]}>
                    {isCurrent ? 'Current plan' : t.cta}
                  </Text>
                </Pressable>
              </View>
            );
          })}
        </View>

        <View style={styles.note}>
          <Ionicons name="shield-checkmark-outline" size={14} color={colors.brand} />
          <Text style={styles.noteText}>
            {paypalLive
              ? `PayPal is live in ${paypalMode} mode. Stripe checkout is simulated.`
              : 'Powered by Stripe and PayPal. Checkout is simulated for demo — plug in real keys anytime.'}
          </Text>
        </View>
      </ScrollView>

      <CheckoutModal
        tier={checkoutTier}
        phase={phase}
        session={session}
        provider={provider}
        setProvider={setProvider}
        onConfirm={confirmCheckout}
        onClose={closeCheckout}
        paypalLive={paypalLive}
        paypalMode={paypalMode}
        errorMsg={errorMsg}
        onRetry={() => setPhase('method')}
      />
    </View>
  );
}


function CheckoutModal({
  tier, phase, session, provider, setProvider, onConfirm, onClose,
  paypalLive, paypalMode, errorMsg, onRetry,
}: {
  tier: any;
  phase: CheckoutPhase;
  session: any;
  provider: 'stripe' | 'paypal';
  setProvider: (p: 'stripe' | 'paypal') => void;
  onConfirm: () => void;
  onClose: () => void;
  paypalLive: boolean;
  paypalMode: string | null;
  errorMsg: string | null;
  onRetry: () => void;
}) {
  if (!tier || phase === 'idle') return null;
  const busy = phase === 'creating' || phase === 'processing';

  return (
    <Modal transparent animationType="fade" visible onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalSheet}>
          <View style={styles.modalHead}>
            <View>
              <Text style={styles.modalKicker}>CHECKOUT</Text>
              <Text style={styles.modalTitle}>Upgrade to {tier.name}</Text>
            </View>
            {!busy && (
              <Pressable onPress={onClose} style={styles.modalClose} testID="checkout-close">
                <Ionicons name="close" size={20} color={colors.onSurfaceSecondary} />
              </Pressable>
            )}
          </View>

          <View style={styles.summaryBox}>
            <Text style={styles.summaryLabel}>Amount due today</Text>
            <View style={styles.summaryPriceRow}>
              <Text style={styles.summaryCurrency}>$</Text>
              <Text style={styles.summaryPrice}>{tier.price_monthly}</Text>
              <Text style={styles.summaryUnit}>/mo</Text>
            </View>
            <Text style={styles.summaryDesc}>Billed monthly · Cancel anytime</Text>
          </View>

          {phase === 'method' && (
            <>
              <Text style={styles.pickerLabel}>Payment method</Text>
              <View style={{ gap: spacing.sm }}>
                <PaymentOption
                  id="stripe"
                  name="Card via Stripe"
                  desc="Visa, Mastercard, Amex"
                  icon="card"
                  color="#635BFF"
                  selected={provider === 'stripe'}
                  onPress={() => setProvider('stripe')}
                />
                <PaymentOption
                  id="paypal"
                  name={paypalLive ? `PayPal · ${(paypalMode ?? 'live').toUpperCase()}` : 'PayPal'}
                  desc={paypalLive ? 'Real PayPal Checkout' : 'Pay with your PayPal balance'}
                  icon="wallet"
                  color="#0070BA"
                  selected={provider === 'paypal'}
                  onPress={() => setProvider('paypal')}
                  live={paypalLive}
                />
              </View>
              <Pressable onPress={onConfirm} style={styles.payBtn} testID="checkout-confirm">
                <Ionicons name="lock-closed" size={14} color={colors.onBrandPrimary} />
                <Text style={styles.payBtnText}>Pay ${tier.price_monthly} securely</Text>
              </Pressable>
              <Text style={styles.disclaimer}>
                {provider === 'paypal' && paypalLive
                  ? `PayPal will open in a secure browser window for approval.`
                  : `Your subscription auto-renews monthly. Cancel anytime in Profile.`}
              </Text>
            </>
          )}

          {phase === 'error' && (
            <View style={styles.processingBlock}>
              <View style={styles.errorCircle}>
                <Ionicons name="alert" size={28} color={colors.error} />
              </View>
              <Text style={styles.processingTitle}>{`Checkout couldn't complete`}</Text>
              <Text style={styles.processingSub}>{errorMsg ?? 'Please try again.'}</Text>
              <View style={{ flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm }}>
                <Pressable onPress={onClose} style={styles.retryBtnGhost} testID="checkout-cancel-error">
                  <Text style={styles.retryBtnGhostText}>Cancel</Text>
                </Pressable>
                <Pressable onPress={onRetry} style={styles.retryBtn} testID="checkout-retry">
                  <Text style={styles.retryBtnText}>Try again</Text>
                </Pressable>
              </View>
            </View>
          )}

          {(phase === 'creating' || phase === 'processing') && (
            <View style={styles.processingBlock}>
              <ActivityIndicator size="large" color={colors.brand} />
              <Text style={styles.processingTitle}>
                {phase === 'creating' ? 'Creating checkout…' : `Confirming with ${provider === 'stripe' ? 'Stripe' : 'PayPal'}…`}
              </Text>
              <Text style={styles.processingSub}>
                {phase === 'creating' ? 'Setting up secure session' : 'Processing your payment'}
              </Text>
              {session?.session_id && (
                <Text style={styles.sessionId} numberOfLines={1}>Session · {session.session_id.slice(0, 24)}…</Text>
              )}
            </View>
          )}

          {phase === 'success' && (
            <View style={styles.processingBlock}>
              <View style={styles.successCircle}>
                <Ionicons name="checkmark" size={32} color={colors.success} />
              </View>
              <Text style={styles.processingTitle}>{`You're on ${tier.name}!`}</Text>
              <Text style={styles.processingSub}>All Pro features unlocked instantly.</Text>
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
}


function PaymentOption({
  id, name, desc, icon, color, selected, onPress, live,
}: {
  id: string; name: string; desc: string; icon: any; color: string;
  selected: boolean; onPress: () => void; live?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.payOption, selected && { borderColor: color, backgroundColor: `${color}14` }]}
      testID={`method-${id}`}
    >
      <View style={[styles.payIcon, { backgroundColor: `${color}22` }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <View style={styles.payNameRow}>
          <Text style={styles.payName}>{name}</Text>
          {live && (
            <View style={styles.livePill}>
              <View style={styles.livePulse} />
              <Text style={styles.livePillText}>LIVE</Text>
            </View>
          )}
        </View>
        <Text style={styles.payDesc}>{desc}</Text>
      </View>
      <View style={[styles.radio, selected && { borderColor: color }]}>
        {selected && <View style={[styles.radioDot, { backgroundColor: color }]} />}
      </View>
    </Pressable>
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
    flexDirection: 'row', gap: spacing.sm, alignItems: 'center',
    marginTop: spacing.xl, padding: spacing.md,
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  noteText: { color: colors.onSurface, fontSize: 11, flex: 1, lineHeight: 16 },

  // Checkout modal
  modalBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.75)',
    justifyContent: 'center', alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  modalSheet: {
    width: '100%', maxWidth: 460,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: spacing.md,
  },
  modalHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  modalKicker: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1.2, fontWeight: '700' },
  modalTitle: { color: colors.onSurface, fontSize: 20, fontWeight: '700', marginTop: 2, letterSpacing: -0.4 },
  modalClose: {
    width: 30, height: 30, borderRadius: 15,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.surfaceTertiary,
  },

  summaryBox: {
    backgroundColor: colors.surface,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    gap: 2,
  },
  summaryLabel: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 0.6, fontWeight: '600' },
  summaryPriceRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: 4 },
  summaryCurrency: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  summaryPrice: { color: colors.onSurface, fontSize: 30, fontWeight: '700', letterSpacing: -1 },
  summaryUnit: { color: colors.onSurfaceTertiary, fontSize: 12, marginLeft: 4 },
  summaryDesc: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 2 },

  pickerLabel: { color: colors.onSurfaceSecondary, fontSize: 11, letterSpacing: 0.8, fontWeight: '700', marginTop: spacing.sm },

  payOption: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.sm, padding: spacing.md,
    borderWidth: 1.5, borderColor: colors.border,
  },
  payIcon: {
    width: 32, height: 32, borderRadius: 16,
    alignItems: 'center', justifyContent: 'center',
  },
  payName: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  payDesc: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: 1 },
  radio: {
    width: 18, height: 18, borderRadius: 9,
    borderWidth: 1.5, borderColor: colors.borderStrong,
    alignItems: 'center', justifyContent: 'center',
  },
  radioDot: { width: 8, height: 8, borderRadius: 4 },

  payBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: colors.brand,
    paddingVertical: 14, borderRadius: radius.md,
    marginTop: spacing.sm,
  },
  payBtnText: { color: colors.onBrandPrimary, fontSize: 15, fontWeight: '700', letterSpacing: -0.2 },
  disclaimer: { color: colors.onSurfaceTertiary, fontSize: 10, textAlign: 'center', lineHeight: 14 },

  processingBlock: {
    alignItems: 'center', paddingVertical: spacing.xl, gap: spacing.md,
  },
  processingTitle: { color: colors.onSurface, fontSize: 16, fontWeight: '700', marginTop: spacing.md, textAlign: 'center' },
  processingSub: { color: colors.onSurfaceTertiary, fontSize: 12, textAlign: 'center' },
  sessionId: { color: colors.onSurfaceTertiary, fontSize: 10, fontFamily: 'monospace' },
  successCircle: {
    width: 68, height: 68, borderRadius: 34,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(69,201,122,0.18)',
    borderWidth: 2, borderColor: 'rgba(69,201,122,0.66)',
  },
  errorCircle: {
    width: 60, height: 60, borderRadius: 30,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(229,72,77,0.16)',
    borderWidth: 2, borderColor: 'rgba(229,72,77,0.5)',
  },
  retryBtn: {
    backgroundColor: colors.brand,
    paddingHorizontal: spacing.lg, paddingVertical: 10,
    borderRadius: radius.sm,
  },
  retryBtnText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: '700' },
  retryBtnGhost: {
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
    paddingHorizontal: spacing.lg, paddingVertical: 10,
    borderRadius: radius.sm,
  },
  retryBtnGhostText: { color: colors.onSurfaceSecondary, fontSize: 13, fontWeight: '600' },

  payNameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  livePill: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: 'rgba(69,201,122,0.14)',
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4,
  },
  livePulse: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: colors.success },
  livePillText: { color: colors.success, fontSize: 8, fontWeight: '800', letterSpacing: 0.6 },
});
