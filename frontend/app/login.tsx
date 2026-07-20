import { useState } from 'react';
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
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
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        {/* TOP — objective front and center */}
        <View style={styles.top}>
          <View style={styles.brandRow}>
            <View style={styles.logoMark}>
              <Ionicons name="sparkles" size={16} color={colors.brand} />
            </View>
            <Text style={styles.brand}>CreatorOS</Text>
          </View>

          <Text style={styles.objective} testID="login-objective">
            The AI business OS for creators.
          </Text>

          <Text style={styles.purpose}>
            Track your revenue, benchmark against the top 1%, and generate growth plans — all from one place.
          </Text>
        </View>

        {/* BOTTOM — sign in */}
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
  safe: { flex: 1, paddingHorizontal: spacing.xl, justifyContent: 'space-between' },

  top: { paddingTop: spacing.xl },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xxxl },
  logoMark: {
    width: 28, height: 28, borderRadius: 8,
    backgroundColor: colors.brandTertiary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.brand,
  },
  brand: { color: colors.onSurface, fontSize: 15, fontWeight: '600', letterSpacing: -0.2 },

  objective: {
    color: colors.onSurface,
    fontSize: 34,
    fontWeight: '700',
    letterSpacing: -1.2,
    lineHeight: 40,
  },
  purpose: {
    color: colors.onSurfaceSecondary,
    fontSize: 15,
    lineHeight: 22,
    marginTop: spacing.md,
    maxWidth: 340,
  },

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
