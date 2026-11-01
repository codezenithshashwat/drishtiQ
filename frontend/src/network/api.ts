// Typed client for /api/network/*. Same origin, so the HttpOnly session cookie travels automatically. State-changing
// requests carry X-Requested-With (the server's CSRF guard).
export type Lang = 'hi' | 'en'
export type Verification = 'verified' | 'unverified' | 'simulated'
export type CampState = 'open' | 'full' | 'closed' | 'expired' | 'cancelled'
export type RegStatus = 'interest_received' | 'contacted' | 'confirmed_by_organiser' | 'attended' | 'no_show' | 'cancelled'
export type Role = 'user' | 'health_worker' | 'organiser' | 'admin'

export type Camp = {
  id: number
  title: { hi: string; en: string }
  starts_at: string
  ends_at: string
  place: { label: string; village: string | null; district: string; state: string; pin: string }
  organiser: { name: string; kind: string; verification: Verification }
  verification: Verification
  is_demo: boolean
  state: CampState
  planned_capacity: number | null
  price: string | null
  contact: string | null
  publish_state: 'draft' | 'published' | 'closed' | 'cancelled'
  match?: 'exact' | 'nearby' | 'text' | null
  counts?: Partial<Record<RegStatus, number>>
  price_info?: string | null
  contact_public?: string | null
  interest_total?: number
}
/** Patient-safe screening status (backend/network/bridge.py): never a stage, image, prediction or clinical record. */
export type Screening = {
  state: 'not_linked' | 'in_progress' | 'incomplete' | 'quality_check' | 'awaiting_review' | 'decision_recorded' | 'unavailable'
  next_action?: 'urgent_referral' | 'referral' | 'examination' | 'recapture' | 'follow_up' | 'routine_rescreen' | null
  missing_eyes?: ('right' | 'left')[]; quality_provisional?: boolean; eyes_awaiting_review?: number; decided_at?: string | null
}
export type CampSearch = { items: Camp[]; exact: number; nearby: number; query: { pin: string | null; q: string | null } }
export type Registration = {
  id?: number
  ref: string
  status: RegStatus
  created_at: string
  updated_at: string
  channel: 'self' | 'assisted' | 'saathi_guided'
  name: string
  pin: string
  village: string | null
  language: Lang
  camp: Camp
  phone_masked?: string | null
  phone?: string | null
  email?: string | null
  contact_consent?: boolean
  screening?: Screening
}
export type RegResult = { registration: Registration; receipt_code: string | null; duplicate: boolean; replayed: boolean }
export type User = {
  id: number; role: Role; name: string; identifier_type: 'mobile' | 'email'; identifier_masked: string; identifier_verified: boolean
  village: string | null; pin: string | null; language: Lang; reminders_opt_in: boolean; comm_pref: 'none' | 'sms' | 'call' | 'email'
  is_prototype: boolean; created_at: string
}
export type Topic = { slug: string; icon: string; title: string; summary: string; review_status: string; blocks?: { h: string; p: string }[] }
export type Followup = { id: number; kind: string; status: string; due_at: string | null; note: string | null; ref: string; name: string; phone: string | null; camp: Camp }
export type OrgSummary = {
  camps: number; open_camps: number; interest_total: number; planned_capacity_open: number
  status_totals: Record<RegStatus, number>; interest_by_pin: { pin: string; n: number }[]; is_demo_data: boolean
}
export type SaathiCard =
  | { type: 'camps'; items: { id: number; title: string; starts_at: string; village: string; district: string; pin: string; verification: Verification; state: CampState; is_demo: boolean; match?: string | null }[] }
  | { type: 'topic'; slug: string; title: string; summary: string; review_status: string }
  | { type: 'profile'; profile: User }
  | { type: 'registrations'; items: { ref: string; title: string; starts_at: string; status: RegStatus; status_label: string }[] }
export type SaathiAction =
  | { type: 'navigate'; to: string }
  | { type: 'open_registration'; camp_id: number; prefill: { pin?: string; language?: Lang } }
  | { type: 'set_language'; lang: Lang }
export type SaathiTurn = {
  reply: { text: string; lang: Lang }
  cards: SaathiCard[]
  links: { label: string; to: string }[]
  actions: SaathiAction[]
  suggestions: string[]
  state: Record<string, unknown>
  meta: { provider: 'rules' | 'gemini'; degraded: boolean; intent: string }
}
export type PublicConfig = { demo_mode: boolean; saathi: { providers: string[] }; consent_version: string; retention_days: number }

export class NetError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message) }
}

async function req<T>(path: string, init?: RequestInit & { json?: unknown; timeout?: number }): Promise<T> {
  const ctl = new AbortController()
  const timer = window.setTimeout(() => ctl.abort(), init?.timeout ?? 15000)
  const headers: Record<string, string> = { 'X-Requested-With': 'dqn' }
  let body: BodyInit | undefined
  if (init?.json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(init.json) }
  try {
    const r = await fetch(`/api/network${path}`, { method: init?.method ?? (body ? 'POST' : 'GET'), headers, body, signal: ctl.signal, credentials: 'same-origin' })
    if (!r.ok) {
      let code = `http_${r.status}`, msg = `Request failed (${r.status})`
      try {
        const b = await r.json()
        if (b?.detail?.code) { code = b.detail.code; msg = b.detail.message }
        else if (Array.isArray(b?.detail)) { code = 'invalid_input'; msg = b.detail.map((d: { loc?: string[] }) => d.loc?.slice(-1)[0]).join(', ') }
        else if (typeof b?.detail === 'string') msg = b.detail
      } catch { /* not JSON */ }
      throw new NetError(code, msg, r.status)
    }
    return (await r.json()) as T
  } catch (e) {
    if (e instanceof NetError) throw e
    throw new NetError(ctl.signal.aborted ? 'timeout' : 'network', 'The service could not be reached.')
  } finally { window.clearTimeout(timer) }
}

const qs = (o: Record<string, string | number | boolean | null | undefined>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(o)) if (v !== null && v !== undefined && v !== '' && v !== false) p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const net = {
  config: () => req<PublicConfig>('/public/config'),
  summary: () => req<{ open_camps: number; all_demo: boolean }>('/public/summary'),
  camps: (p: { pin?: string | null; q?: string | null; include_expired?: boolean }) => req<CampSearch>(`/camps${qs(p)}`),
  camp: (id: number) => req<Camp>(`/camps/${id}`),
  topics: (lang: Lang) => req<{ items: Topic[] }>(`/content?lang=${lang}`),
  topic: (slug: string, lang: Lang) => req<Topic>(`/content/${slug}?lang=${lang}`),
  register: (b: { camp_id: number; name: string; pin: string; village?: string; phone?: string; email?: string; language: Lang; consent: boolean; contact_consent: boolean; idempotency_key: string; via_saathi?: boolean }) =>
    req<RegResult>('/registrations', { json: b }),
  lookup: (ref: string, code: string) => req<Registration>('/registrations/lookup', { json: { ref, code } }),
  signup: (b: { name: string; identifier: string; password: string; village?: string; pin?: string; language: Lang; reminders_opt_in: boolean; comm_pref: string; consent: boolean }) =>
    req<{ user: User }>('/auth/signup', { json: b }),
  login: (identifier: string, password: string) => req<{ user: User }>('/auth/login', { json: { identifier, password } }),
  logout: () => req<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
  me: () => req<{ user: User | null }>('/me'),
  updateMe: (b: Partial<{ name: string; village: string; pin: string; language: Lang; reminders_opt_in: boolean; comm_pref: string }>) => req<{ user: User }>('/me', { method: 'PATCH', json: b }),
  deleteMe: () => req<{ ok: boolean }>('/me', { method: 'DELETE' }),
  myRegs: () => req<{ items: Registration[] }>('/me/registrations'),
  exportMe: () => req<unknown>('/me/export'),
  claim: (ref: string, code: string) => req<Registration>('/me/registrations/claim', { json: { ref, code } }),
  cancel: (id: number) => req<Registration>(`/me/registrations/${id}/cancel`, { method: 'POST' }),
  workerCamps: () => req<{ items: Camp[] }>('/worker/camps'),
  workerRequests: (camp_id?: number | null) => req<{ items: Registration[] }>(`/worker/requests${qs({ camp_id })}`),
  workerFollowups: () => req<{ items: Followup[] }>('/worker/followups'),
  completeFollowup: (id: number, note?: string) => req<{ id: number }>(`/worker/followups/${id}`, { method: 'PATCH', json: { note: note || null } }),
  setStatus: (id: number, status: RegStatus) => req<Registration>(`/worker/registrations/${id}/status`, { method: 'PATCH', json: { status } }),
  assisted: (b: { camp_id: number; name: string; pin: string; village?: string; phone?: string; language: Lang; consent: boolean; contact_consent: boolean; consent_spoken_confirmed: boolean; idempotency_key: string }) =>
    req<RegResult>('/worker/registrations', { json: b }),
  orgCamps: () => req<{ items: Camp[] }>('/organiser/camps'),
  orgSummary: () => req<OrgSummary>('/organiser/summary'),
  saveCamp: (id: number | 'new', b: CampForm) => req<Camp>(id === 'new' ? '/organiser/camps' : `/organiser/camps/${id}`, { method: id === 'new' ? 'POST' : 'PATCH', json: b }),
  verifyCamp: (id: number, verification: 'verified' | 'unverified') => req<Camp>(`/admin/camps/${id}/verification`, { method: 'PATCH', json: { verification } }),
  saathi: (b: { text: string; lang: Lang; state: Record<string, unknown>; ui: { screen?: string; camp_id?: number } }) => req<SaathiTurn>('/saathi/turn', { json: b, timeout: 20000 }),
}

export type CampForm = {
  title_en: string; title_hi: string; place_label: string; village: string | null; district: string; state: string; pin: string
  starts_at: string; ends_at: string; capacity: number | null; price_info: string | null; contact_public: string | null
  publish_state: 'draft' | 'published' | 'closed' | 'cancelled'
}
