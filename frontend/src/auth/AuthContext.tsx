/**
 * AuthContext — Emergent Google Auth integration.
 * - On mount: check stored token, validate against /api/auth/me
 * - signIn(): open Emergent auth flow, exchange session_id for token
 * - signOut(): clear server + local
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Platform } from 'react-native';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import * as SecureStore from 'expo-secure-store';
import { startAnalytics, stopAnalytics, track } from '@/src/services/analytics';

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;
const TOKEN_KEY = 'creatoros_session_token';

type User = { user_id: string; email: string; name: string; picture?: string; onboarding_complete?: boolean; youtube_handle?: string | null; instagram_handle?: string | null; tier?: string; demo_mode?: boolean };
type AuthState = {
  loading: boolean;
  user: User | null;
  token: string | null;
  signIn: () => Promise<{ ok: boolean; reason?: string }>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthCtx = createContext<AuthState | null>(null);

async function tokenGet(): Promise<string | null> {
  if (Platform.OS === 'web') return typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_KEY) : null;
  try { return await SecureStore.getItemAsync(TOKEN_KEY); } catch { return null; }
}
async function tokenSet(t: string) {
  if (Platform.OS === 'web') { if (typeof window !== 'undefined') window.localStorage.setItem(TOKEN_KEY, t); return; }
  try { await SecureStore.setItemAsync(TOKEN_KEY, t); } catch {}
}
async function tokenClear() {
  if (Platform.OS === 'web') { if (typeof window !== 'undefined') window.localStorage.removeItem(TOKEN_KEY); return; }
  try { await SecureStore.deleteItemAsync(TOKEN_KEY); } catch {}
}

function parseSessionId(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    const hash = u.hash?.startsWith('#') ? u.hash.slice(1) : u.hash;
    const params = new URLSearchParams(hash || u.search);
    return params.get('session_id');
  } catch {
    return null;
  }
}

async function exchange(session_id: string): Promise<{ token: string; user: User } | null> {
  const r = await fetch(`${BASE}/api/auth/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id }),
  });
  if (!r.ok) return null;
  return r.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const completeAuth = useCallback(async (sid: string) => {
    const result = await exchange(sid);
    if (!result) return false;
    await tokenSet(result.token);
    setToken(result.token);
    setUser(result.user);
    // Fire signup/session start event (fire-and-forget)
    await startAnalytics();
    track('signup_completed', { via: 'google' });
    return true;
  }, []);

  // Bootstrap
  useEffect(() => {
    let alive = true;
    (async () => {
      // Web: check URL for session_id first
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        const sid = parseSessionId(window.location.href);
        if (sid) {
          // Always strip the one-time session_id/state fragment from the
          // URL right away, whether the exchange succeeds or fails. If we
          // only clean it up on success, a failed/expired attempt (e.g.
          // "Invalid state parameter" from a stale or duplicate sign-in
          // attempt) leaves a dead session_id sitting in the address bar —
          // a reload or retry from that URL can then confuse the next
          // attempt instead of starting a clean one.
          window.history.replaceState(null, '', window.location.pathname);
          const ok = await completeAuth(sid);
          if (ok) {
            if (alive) setLoading(false);
            return;
          }
        }
      }
      // Mobile: check initial URL
      if (Platform.OS !== 'web') {
        const initial = await Linking.getInitialURL();
        const sid = parseSessionId(initial);
        if (sid) {
          const ok = await completeAuth(sid);
          if (ok) { if (alive) setLoading(false); return; }
        }
      }

      // Check stored token
      const stored = await tokenGet();
      if (!stored) { if (alive) setLoading(false); return; }
      const r = await fetch(`${BASE}/api/auth/me`, { headers: { Authorization: `Bearer ${stored}` } });
      if (r.ok) {
        const data = await r.json();
        if (alive) { setUser(data.user); setToken(stored); }
        // Boot analytics for returning session
        await startAnalytics();
      } else {
        await tokenClear();
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [completeAuth]);

  // Mobile deep-link listener (hot links)
  useEffect(() => {
    if (Platform.OS === 'web') return;
    const sub = Linking.addEventListener('url', async ({ url }) => {
      const sid = parseSessionId(url);
      if (sid) await completeAuth(sid);
    });
    return () => sub.remove();
  }, [completeAuth]);

  const signIn = useCallback(async () => {
    const isWeb = Platform.OS === 'web';
    const redirectUrl = isWeb
      ? (typeof window !== 'undefined' ? window.location.origin + '/' : '')
      : Linking.createURL('auth');
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;

    if (isWeb) {
      if (typeof window !== 'undefined') window.location.href = authUrl;
      return { ok: true };
    }
    const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
    if (result.type !== 'success' || !result.url) return { ok: false, reason: 'cancelled' };
    const sid = parseSessionId(result.url);
    if (!sid) return { ok: false, reason: 'no_session_id' };
    const ok = await completeAuth(sid);
    return { ok, reason: ok ? undefined : 'exchange_failed' };
  }, [completeAuth]);

  const signOut = useCallback(async () => {
    track('signout');
    if (token) {
      try { await fetch(`${BASE}/api/auth/logout`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }); } catch {}
    }
    await stopAnalytics();
    await tokenClear();
    setToken(null);
    setUser(null);
  }, [token]);

  const refreshUser = useCallback(async () => {
    if (!token) return;
    const r = await fetch(`${BASE}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) {
      const data = await r.json();
      setUser(data.user);
    }
  }, [token]);

  return (
    <AuthCtx.Provider value={{ loading, user, token, signIn, signOut, refreshUser }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
