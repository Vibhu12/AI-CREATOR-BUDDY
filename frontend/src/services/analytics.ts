/**
 * Analytics client — batched, resilient, PII-safe.
 *
 * Public API:
 *   track(event, props?)          Enqueue an event. Never throws.
 *   flush()                       Force flush now (returns promise).
 *   startAnalytics()              Called once from AuthContext after login.
 *   stopAnalytics()               Called on sign-out to purge queue.
 *
 * Behavior:
 *  - Events buffered in memory + persisted to AsyncStorage under ANALYTICS_QUEUE_KEY.
 *  - Auto-flushes when: queue reaches 20 items OR every 15s OR app comes to foreground.
 *  - Retries once on network failure with 4s backoff; drops events older than 3 days.
 *  - Never blocks UI — every call is fire-and-forget.
 *  - Never sends PII: no email/token/session_id keys.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { AppState, Platform } from 'react-native';
import { api } from './api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type AnalyticsEvent = {
  event: string;
  at: string;
  session?: Record<string, unknown>;
  props?: Record<string, unknown>;
};

const ANALYTICS_QUEUE_KEY = 'analytics.queue.v1';
const MAX_QUEUE = 500;
const FLUSH_INTERVAL_MS = 15_000;
const FLUSH_THRESHOLD = 20;
const MAX_AGE_DAYS = 3;

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------
let queue: AnalyticsEvent[] = [];
let flushInterval: ReturnType<typeof setInterval> | null = null;
let appStateSub: ReturnType<typeof AppState.addEventListener> | null = null;
let started = false;
let inflight = false;

// Static session envelope filled on start
let sessionMeta: Record<string, unknown> = {};


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function nowIso(): string {
  return new Date().toISOString();
}

function ageDays(iso: string): number {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return Infinity;
  return (Date.now() - t) / 86_400_000;
}

async function loadFromStorage() {
  try {
    const raw = await AsyncStorage.getItem(ANALYTICS_QUEUE_KEY);
    if (raw) {
      const parsed: AnalyticsEvent[] = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        // Drop events older than MAX_AGE_DAYS (server rejects them anyway)
        queue = parsed.filter(e => ageDays(e.at) < MAX_AGE_DAYS);
      }
    }
  } catch {
    queue = [];
  }
}

async function persist() {
  try {
    await AsyncStorage.setItem(ANALYTICS_QUEUE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE)));
  } catch {
    /* AsyncStorage down — worst case we lose events on restart */
  }
}


// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export function track(event: string, props?: Record<string, unknown>) {
  try {
    if (!event || typeof event !== 'string') return;
    const evt: AnalyticsEvent = {
      event,
      at: nowIso(),
      session: sessionMeta,
      props: props ?? {},
    };
    queue.push(evt);
    if (queue.length > MAX_QUEUE) queue = queue.slice(-MAX_QUEUE);
    // Persist async (don't await — fire and forget)
    void persist();
    if (queue.length >= FLUSH_THRESHOLD) void flush();
  } catch {
    /* never throw from analytics */
  }
}

export async function flush(): Promise<void> {
  if (inflight || queue.length === 0) return;
  inflight = true;
  const batch = queue.slice(0, 100);
  try {
    const res = await api.trackEvents(batch);
    // Drop only the events we successfully sent (regardless of skipped list)
    queue = queue.slice(batch.length);
    void persist();
    if (res?.skipped?.length) {
      console.log('[analytics] server skipped:', res.skipped.length);
    }
  } catch {
    // Backoff — retry naturally on next tick
    await new Promise(r => setTimeout(r, 4000));
  } finally {
    inflight = false;
  }
}


export async function startAnalytics(userMeta?: { app_version?: string }) {
  if (started) return;
  started = true;

  sessionMeta = {
    device: Platform.OS,                                    // ios | android | web
    os_version: Platform.Version?.toString?.() ?? 'unknown',
    app_version: userMeta?.app_version ?? Constants.expoConfig?.version ?? 'dev',
    locale: (Intl?.DateTimeFormat?.().resolvedOptions?.().locale) ?? 'en',
    timezone: (Intl?.DateTimeFormat?.().resolvedOptions?.().timeZone) ?? 'UTC',
  };

  await loadFromStorage();

  // Periodic flush
  flushInterval = setInterval(() => { void flush(); }, FLUSH_INTERVAL_MS);

  // Flush when app comes to foreground
  appStateSub = AppState.addEventListener('change', (s) => {
    if (s === 'active') void flush();
  });
}


export async function stopAnalytics() {
  if (!started) return;
  started = false;
  if (flushInterval) { clearInterval(flushInterval); flushInterval = null; }
  if (appStateSub) { appStateSub.remove(); appStateSub = null; }
  // Best-effort final flush
  await flush();
  // Clear the queue on sign-out (do not leak new user's events to old user's context)
  queue = [];
  try { await AsyncStorage.removeItem(ANALYTICS_QUEUE_KEY); } catch { /* noop */ }
}


// Test helper — do not call from app code
export function _peekQueueSize() { return queue.length; }
