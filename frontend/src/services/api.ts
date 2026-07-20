import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;
const TOKEN_KEY = 'creatoros_session_token';

async function getToken(): Promise<string | null> {
  if (Platform.OS === 'web') return typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_KEY) : null;
  try { return await SecureStore.getItemAsync(TOKEN_KEY); } catch { return null; }
}

async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  const headers: Record<string, string> = { ...(init.headers as any) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetch(`${BASE}${path}`, { ...init, headers });
}

const json = async (r: Response) => {
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

export const api = {
  dashboard:       () => authFetch(`/api/dashboard`).then(json),
  portfolio:       () => authFetch(`/api/portfolio`).then(json),
  createAsset:     (body: any) => authFetch(`/api/portfolio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json),
  content:         () => authFetch(`/api/content`).then(json),
  finance:         () => authFetch(`/api/finance`).then(json),
  goals:           () => authFetch(`/api/goals`).then(json),
  recommendations: () => authFetch(`/api/recommendations`).then(json),

  // Notifications
  notifications:      () => authFetch(`/api/notifications`).then(json),
  markNotification:   (id: string) => authFetch(`/api/notifications/${id}/read`, { method: 'POST' }).then(json),
  markAllNotifications: () => authFetch(`/api/notifications/read-all`, { method: 'POST' }).then(json),

  chatHistory: (session_id: string) => authFetch(`/api/ai/chat/history?session_id=${session_id}`).then(json),
  chatReset:   (session_id: string) => authFetch(`/api/ai/chat/reset?session_id=${session_id}`, { method: 'POST' }).then(json),
  chatUrl:     () => `${BASE}/api/ai/chat`,

  // Competitors
  competitorsRadar: () => authFetch(`/api/competitors/radar`).then(json),
  competitorsGaps:  () => authFetch(`/api/competitors/gaps`).then(json),
  competitorsList:  () => authFetch(`/api/competitors`).then(json),

  // Strategy
  strategyList:     () => authFetch(`/api/strategy/plans`).then(json),
  strategyGenerate: (horizon_days: number, focus?: string) => authFetch(`/api/strategy/plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ horizon_days, focus }),
  }).then(json),
  strategyToggleTask: (plan_id: string, phase_index: number, kind: string, task_index: number, checked: boolean) =>
    authFetch(`/api/strategy/plans/${plan_id}/task`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase_index, kind, task_index, checked }),
    }).then(json),

  // Billing
  billingPlans:   () => authFetch(`/api/billing/plans`).then(json),
  billingPlan:    () => authFetch(`/api/billing/plan`).then(json),
  billingUpgrade: (tier: string) => authFetch(`/api/billing/upgrade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tier }),
  }).then(json),

  // Integrations
  stripeStatus:    () => authFetch(`/api/integrations/stripe/status`).then(json),
  youtubeChannel:  (handle: string) => authFetch(`/api/integrations/youtube/channel?handle=${encodeURIComponent(handle)}`).then(json),
  instagramProfile: (handle: string) => authFetch(`/api/integrations/instagram/profile?handle=${encodeURIComponent(handle)}`).then(json),

  // Auth
  me: () => authFetch(`/api/auth/me`).then(json),

  // Onboarding
  onboardingStatus:   () => authFetch(`/api/onboarding/status`).then(json),
  onboardingComplete: (youtube_handle?: string, instagram_handle?: string) => authFetch(`/api/onboarding/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ youtube_handle, instagram_handle }),
  }).then(json),

  // Dev / reset
  reseedStarter: () => authFetch(`/api/dev/reseed`, { method: 'POST' }).then(json),
};

export { getToken };
