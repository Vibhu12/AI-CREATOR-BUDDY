const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;

const json = async (r: Response) => {
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

export const api = {
  dashboard:       () => fetch(`${BASE}/api/dashboard`).then(json),
  portfolio:       () => fetch(`${BASE}/api/portfolio`).then(json),
  content:         () => fetch(`${BASE}/api/content`).then(json),
  finance:         () => fetch(`${BASE}/api/finance`).then(json),
  goals:           () => fetch(`${BASE}/api/goals`).then(json),
  recommendations: () => fetch(`${BASE}/api/recommendations`).then(json),
  chatHistory:     (session_id: string) => fetch(`${BASE}/api/ai/chat/history?session_id=${session_id}`).then(json),
  chatReset:       (session_id: string) => fetch(`${BASE}/api/ai/chat/reset?session_id=${session_id}`, { method: 'POST' }).then(json),
  chatUrl:         () => `${BASE}/api/ai/chat`,
};
