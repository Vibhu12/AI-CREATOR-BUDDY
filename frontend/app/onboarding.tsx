import { useState } from 'react';
import {
  View, Text, StyleSheet, Pressable, TextInput, ActivityIndicator, ScrollView,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { api } from '@/src/services/api';
import { useAuth } from '@/src/auth/AuthContext';

const STEPS = ['welcome', 'youtube', 'stripe', 'done'] as const;
type Step = typeof STEPS[number];

export default function Onboarding() {
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState<Step>('welcome');
  const [handle, setHandle] = useState('');
  const [preview, setPreview] = useState<any>(null);
  const [lookupErr, setLookupErr] = useState<string | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [busy, setBusy] = useState(false);

  const stepIdx = STEPS.indexOf(step);

  const lookupYoutube = async () => {
    if (!handle.trim()) return;
    setLookingUp(true); setLookupErr(null); setPreview(null);
    try {
      const data = await api.youtubeChannel(handle.trim());
      setPreview(data);
    } catch {
      setLookupErr('Live lookup unavailable — we&apos;ll save your handle for later');
    } finally {
      setLookingUp(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      await api.onboardingComplete(handle.trim() || undefined);
      await refreshUser();
      // Gate will auto-redirect to /(tabs) once user.onboarding_complete flips true
    } catch (e) {
      console.warn(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.root}>
      <LinearGradient colors={['#1C1408', '#0A0805', colors.surface]} style={StyleSheet.absoluteFill} />
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={styles.progress}>
          {STEPS.slice(0, -1).map((_, i) => (
            <View
              key={i}
              style={[styles.progressBar, i <= stepIdx && styles.progressBarActive]}
            />
          ))}
        </View>

        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {step === 'welcome' && (
              <View style={styles.stepBlock}>
                <View style={styles.stepIcon}>
                  <Ionicons name="sparkles" size={26} color={colors.brand} />
                </View>
                <Text style={styles.kicker}>WELCOME</Text>
                <Text style={styles.headline}>
                  Hi {user?.name?.split(' ')[0] || 'there'} — let&apos;s set up your OS.
                </Text>
                <Text style={styles.sub}>
                  In 60 seconds, we&apos;ll connect your first channel and start tracking your business. Your starter dashboard is already loaded with sample data so you can explore.
                </Text>
                <View style={styles.checklist}>
                  {[
                    'Connect your YouTube channel (optional)',
                    'Connect Stripe for live revenue (optional)',
                    'Meet your AI Coach',
                  ].map(t => (
                    <View key={t} style={styles.checkRow}>
                      <Ionicons name="checkmark-circle" size={16} color={colors.brand} />
                      <Text style={styles.checkText}>{t}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {step === 'youtube' && (
              <View style={styles.stepBlock}>
                <View style={[styles.stepIcon, { backgroundColor: 'rgba(255,61,61,0.12)', borderColor: '#FF3D3D' }]}>
                  <Ionicons name="logo-youtube" size={26} color="#FF3D3D" />
                </View>
                <Text style={styles.kicker}>STEP 2 · YOUTUBE</Text>
                <Text style={styles.headline}>Connect your channel</Text>
                <Text style={styles.sub}>
                  Drop your handle so we can pull your subs, views, and video count.
                </Text>
                <View style={styles.inputRow}>
                  <Text style={styles.inputPrefix}>@</Text>
                  <TextInput
                    value={handle}
                    onChangeText={setHandle}
                    placeholder="yourhandle"
                    placeholderTextColor={colors.onSurfaceTertiary}
                    style={styles.input}
                    autoCapitalize="none"
                    autoCorrect={false}
                    testID="onboarding-yt-input"
                  />
                  <Pressable
                    onPress={lookupYoutube}
                    disabled={!handle.trim() || lookingUp}
                    style={[styles.lookupBtn, (!handle.trim() || lookingUp) && { opacity: 0.5 }]}
                    testID="onboarding-yt-lookup"
                  >
                    {lookingUp
                      ? <ActivityIndicator size="small" color={colors.brand} />
                      : <Ionicons name="search" size={14} color={colors.brand} />
                    }
                  </Pressable>
                </View>
                {preview && (
                  <View style={styles.previewCard} testID="onboarding-yt-preview">
                    <Text style={styles.previewTitle} numberOfLines={1}>{preview.title}</Text>
                    <View style={styles.previewStats}>
                      <View style={styles.previewStat}>
                        <Text style={styles.previewValue}>{Number(preview.subscribers).toLocaleString()}</Text>
                        <Text style={styles.previewLabel}>SUBS</Text>
                      </View>
                      <View style={styles.previewStat}>
                        <Text style={styles.previewValue}>{Number(preview.views).toLocaleString()}</Text>
                        <Text style={styles.previewLabel}>VIEWS</Text>
                      </View>
                      <View style={styles.previewStat}>
                        <Text style={styles.previewValue}>{preview.videos}</Text>
                        <Text style={styles.previewLabel}>VIDEOS</Text>
                      </View>
                    </View>
                  </View>
                )}
                {lookupErr && <Text style={styles.warn}>{lookupErr}</Text>}
                <Text style={styles.skipHint}>Skip if you don&apos;t have one — you can add later.</Text>
              </View>
            )}

            {step === 'stripe' && (
              <View style={styles.stepBlock}>
                <View style={[styles.stepIcon, { backgroundColor: 'rgba(127,179,255,0.12)', borderColor: '#7FB3FF' }]}>
                  <Ionicons name="card" size={26} color="#7FB3FF" />
                </View>
                <Text style={styles.kicker}>STEP 3 · STRIPE</Text>
                <Text style={styles.headline}>Connect Stripe for live revenue</Text>
                <Text style={styles.sub}>
                  Once connected, your Finance tab shows real balance, payouts, and recent charges. We only read — never write.
                </Text>
                <View style={styles.stripeCard}>
                  <Ionicons name="lock-closed" size={16} color={colors.brand} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.stripeCardTitle}>Coming soon</Text>
                    <Text style={styles.stripeCardSub}>
                      Stripe OAuth is being wired up. For now, we&apos;ll show your starter data.
                    </Text>
                  </View>
                </View>
                <Text style={styles.skipHint}>Tap Finish to enter CreatorOS.</Text>
              </View>
            )}

            {step === 'done' && (
              <View style={styles.stepBlock}>
                <View style={styles.stepIcon}>
                  <Ionicons name="checkmark-circle" size={30} color={colors.success} />
                </View>
                <Text style={styles.kicker}>YOU&apos;RE IN</Text>
                <Text style={styles.headline}>All set.</Text>
                <Text style={styles.sub}>
                  Your dashboard is ready. Say hi to your AI Coach anytime.
                </Text>
              </View>
            )}
          </ScrollView>

          <View style={styles.footer}>
            {stepIdx > 0 && stepIdx < STEPS.length - 1 && (
              <Pressable
                onPress={() => setStep(STEPS[Math.max(0, stepIdx - 1)])}
                style={styles.secondaryBtn}
                testID="onboarding-back-btn"
              >
                <Text style={styles.secondaryBtnText}>Back</Text>
              </Pressable>
            )}
            <Pressable
              onPress={() => {
                if (step === 'stripe') {
                  setStep('done');
                  return;
                }
                if (step === 'done') {
                  finish();
                  return;
                }
                const next = STEPS[Math.min(STEPS.length - 1, stepIdx + 1)];
                setStep(next);
              }}
              disabled={busy}
              style={[styles.primaryBtn, busy && { opacity: 0.6 }]}
              testID="onboarding-next-btn"
            >
              {busy
                ? <ActivityIndicator color={colors.onBrandPrimary} />
                : (
                  <>
                    <Text style={styles.primaryBtnText}>
                      {step === 'done' ? 'Enter CreatorOS' : step === 'stripe' ? 'Finish' : step === 'welcome' ? 'Get started' : 'Continue'}
                    </Text>
                    <Ionicons name="arrow-forward" size={16} color={colors.onBrandPrimary} />
                  </>
                )
              }
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  safe: { flex: 1, paddingHorizontal: spacing.xl },
  progress: { flexDirection: 'row', gap: 6, marginTop: spacing.md },
  progressBar: { flex: 1, height: 3, borderRadius: 2, backgroundColor: colors.surfaceTertiary },
  progressBarActive: { backgroundColor: colors.brand },

  content: { paddingVertical: spacing.xl, flexGrow: 1 },
  stepBlock: { flex: 1, justifyContent: 'center', gap: spacing.md },
  stepIcon: {
    width: 56, height: 56, borderRadius: 12,
    backgroundColor: colors.brandTertiary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  kicker: { color: colors.brand, fontSize: 11, letterSpacing: 1.4, fontWeight: '700' },
  headline: { color: colors.onSurface, fontSize: 30, fontWeight: '700', letterSpacing: -1, lineHeight: 36 },
  sub: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 20, maxWidth: 340 },

  checklist: { marginTop: spacing.md, gap: spacing.sm },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  checkText: { color: colors.onSurface, fontSize: 13 },

  inputRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.surfaceSecondary, borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    paddingHorizontal: spacing.md, marginTop: spacing.md,
  },
  inputPrefix: { color: colors.onSurfaceTertiary, fontSize: 15 },
  input: { flex: 1, color: colors.onSurface, fontSize: 15, paddingVertical: 12, paddingHorizontal: 4 },
  lookupBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.brandTertiary,
    alignItems: 'center', justifyContent: 'center',
  },

  previewCard: {
    backgroundColor: colors.surfaceSecondary, borderRadius: radius.md,
    padding: spacing.md, marginTop: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  previewTitle: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
  previewStats: { flexDirection: 'row', marginTop: spacing.sm, gap: spacing.lg },
  previewStat: { alignItems: 'flex-start' },
  previewValue: { color: colors.brand, fontSize: 18, fontWeight: '700' },
  previewLabel: { color: colors.onSurfaceTertiary, fontSize: 9, letterSpacing: 0.8, fontWeight: '700' },

  warn: { color: colors.warning, fontSize: 12, marginTop: spacing.sm },
  skipHint: { color: colors.onSurfaceTertiary, fontSize: 11, marginTop: spacing.md },

  stripeCard: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md, padding: spacing.md, marginTop: spacing.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  stripeCardTitle: { color: colors.onSurface, fontSize: 13, fontWeight: '600' },
  stripeCardSub: { color: colors.onSurfaceSecondary, fontSize: 12, marginTop: 2 },

  footer: { flexDirection: 'row', gap: spacing.sm, paddingBottom: spacing.md },
  primaryBtn: {
    flex: 1,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: radius.md, paddingVertical: 14,
  },
  primaryBtnText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: '700' },
  secondaryBtn: {
    paddingHorizontal: spacing.lg, paddingVertical: 14,
    borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  secondaryBtnText: { color: colors.onSurface, fontSize: 14, fontWeight: '600' },
});
