import { useState } from 'react';
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { useAuth } from '@/src/auth/AuthContext';

export default function Login() {
  const { signIn } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSignIn = async () => {
    setBusy(true); setErr(null);
    const r = await signIn();
    if (!r.ok) setErr(r.reason === 'cancelled' ? 'Sign-in cancelled' : 'Sign-in failed — try again');
    setBusy(false);
  };

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={['#1C1408', '#0A0805', colors.surface]}
        style={StyleSheet.absoluteFill}
      />
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={styles.brandRow}>
          <View style={styles.logoMark}>
            <Ionicons name="sparkles" size={20} color={colors.brand} />
          </View>
          <Text style={styles.brand}>CreatorOS</Text>
        </View>

        <View style={styles.center}>
          <Text style={styles.kicker}>YOUR AI BUSINESS OS</Text>
          <Text style={styles.headline}>The CEO in your pocket.</Text>
          <Text style={styles.sub}>
            Track revenue, predict growth, and run your creator business with a quantified AI co-founder.
          </Text>

          <View style={styles.bullets}>
            {[
              { icon: 'flash', text: 'AI Coach trained on your business' },
              { icon: 'analytics', text: 'Hero score across 6 dimensions' },
              { icon: 'trophy', text: 'Benchmark vs the top 1%' },
              { icon: 'rocket', text: 'AI-generated 30/60/90 day plans' },
            ].map(b => (
              <View key={b.text} style={styles.bulletRow}>
                <Ionicons name={b.icon as any} size={14} color={colors.brand} />
                <Text style={styles.bulletText}>{b.text}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.bottom}>
          {err && <Text style={styles.err}>{err}</Text>}
          <Pressable
            onPress={handleSignIn}
            disabled={busy}
            style={({ pressed }) => [styles.btn, pressed && { opacity: 0.85 }, busy && { opacity: 0.6 }]}
            testID="login-google-btn"
          >
            {busy
              ? <ActivityIndicator color={colors.onBrandPrimary} />
              : (
                <>
                  <Ionicons name="logo-google" size={18} color={colors.onBrandPrimary} />
                  <Text style={styles.btnText}>Continue with Google</Text>
                </>
              )
            }
          </Pressable>
          <Text style={styles.disclaimer}>
            By continuing you agree to CreatorOS&apos;s terms and privacy policy.
          </Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  safe: { flex: 1, paddingHorizontal: spacing.xl },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  logoMark: {
    width: 32, height: 32, borderRadius: 8,
    backgroundColor: colors.brandTertiary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  brand: { color: colors.onSurface, fontSize: 16, fontWeight: '600', letterSpacing: -0.3 },

  center: { flex: 1, justifyContent: 'center' },
  kicker: { color: colors.brand, fontSize: 11, letterSpacing: 1.4, fontWeight: '700' },
  headline: { color: colors.onSurface, fontSize: 36, fontWeight: '700', letterSpacing: -1.2, marginTop: spacing.sm, lineHeight: 42 },
  sub: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 20, marginTop: spacing.md, maxWidth: 320 },

  bullets: { marginTop: spacing.xl, gap: spacing.md },
  bulletRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  bulletText: { color: colors.onSurface, fontSize: 13 },

  bottom: { paddingBottom: spacing.md, gap: spacing.sm },
  err: { color: colors.error, fontSize: 12, textAlign: 'center' },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: radius.md, paddingVertical: 14,
  },
  btnText: { color: colors.onBrandPrimary, fontSize: 15, fontWeight: '700', letterSpacing: -0.2 },
  disclaimer: { color: colors.onSurfaceTertiary, fontSize: 11, textAlign: 'center', marginTop: spacing.xs },
});
