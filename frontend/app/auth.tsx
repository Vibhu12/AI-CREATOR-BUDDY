import { useEffect, useRef } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { colors, spacing } from '@/src/theme/tokens';
import { useAuth } from '@/src/auth/AuthContext';

/**
 * Deep-link landing screen for Emergent Google Auth.
 * The OAuth redirect (frontend://auth#session_id=...) lands here.
 * AuthContext's Linking listener / bootstrap effect performs the actual
 * session exchange in the background — this screen just shows a spinner
 * and then hands off navigation to the root Gate once `user`/`loading`
 * settle, with a safety-net redirect if nothing happens in time.
 */
export default function AuthCallback() {
  const router = useRouter();
  const { loading, user } = useAuth();
  const navigatedRef = useRef(false);

  useEffect(() => {
    if (navigatedRef.current) return;

    if (user) {
      navigatedRef.current = true;
      router.replace(user.onboarding_complete ? '/(tabs)' : '/onboarding');
      return;
    }

    if (!loading) {
      // Bootstrap already finished but the deep-link exchange may still be
      // in flight (hot-link case) — give it a short grace window.
      const t = setTimeout(() => {
        if (!navigatedRef.current) {
          navigatedRef.current = true;
          router.replace('/login');
        }
      }, 4000);
      return () => clearTimeout(t);
    }
  }, [loading, user, router]);

  return (
    <View style={styles.root}>
      <ActivityIndicator color={colors.brand} size="large" />
      <Text style={styles.text}>Signing you in…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.md, backgroundColor: colors.surface },
  text: { color: colors.onSurfaceSecondary, fontSize: 13, fontWeight: '500' },
});
