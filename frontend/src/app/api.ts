// Typed client for the backend. The analysis record is produced by src/inference/pipeline.py; assist by src/inference/assist.py.
export type LesionKey = 'MA' | 'HE' | 'EX' | 'SE'
export type Mode = 'simple' | 'clinical'
export type Eye = 'right' | 'left' | 'unknown'

export type Quality = { usable: boolean; issues: string[]; fov_fraction: number; brightness: number | null; sharpness: number | null }
export type Lesion = { key: LesionKey; name: string; color: string; components: number; area_percent_of_field: number; overlay: string }
export type Region = { id: string; x: number; y: number; area_px: number; quadrant: string; distance_to_fovea_dd: number }
export type Sentence = {
  id: string
  section: 'summary' | 'evidence' | 'reasoning' | 'macula' | 'limits' | 'flags'
  text: string
  simple: string
  clinical: string
  refs?: { lesions?: LesionKey[]; quadrants?: string[]; landmarks?: string[] }
}
export type Findings = {
  landmarks: {
    optic_disc: { x: number; y: number; radius_px: number }
    fovea: { x: number; y: number; uncertain: boolean }
    disc_diameter_px: number
  }
  lesions: Record<LesionKey, { name: string; count: number; area_px: number; per_quadrant: Record<string, number>; regions: Region[] }>
  haemorrhage_quadrants: { count: number; quadrants: string[]; max_per_quadrant: number }
  macular_edema_risk: { level: 'high' | 'possible' | 'low'; reason: string; nearest_exudate_dd: number | null; exudates_within_1dd: number; landmarks_uncertain: boolean }
}
export type Analysis = {
  status: 'ok' | 'rejected'
  model_version: string
  image: { width: number; height: number }
  quality: Quality
  display_image: string
  processing_seconds?: number
  grading?: { grade: number; label: string; low_confidence: boolean; score?: number | null; thresholds?: number[] | null; grader?: string }
  attribution?: { method: string; overlay: string; note: string }
  lesions?: Lesion[]
  consistency_flags?: string[]
  findings?: Findings
  explanations?: Sentence[]
  recommendation?: string
  disclaimer?: string
}
export type Assist = {
  available: boolean
  defer: boolean
  reason: string | null
  p_referable?: number
  stage_confidence?: number
  tau?: number
  confidence_level?: 'high' | 'moderate' | 'low'
}
export type RoutingState = 'URGENT_REVIEW' | 'CLINICIAN_REVIEW' | 'REFERABLE' | 'RETAKE' | 'ROUTINE_RESCREEN_ELIGIBLE' | 'INCOMPLETE_SCREENING'
export type Routing = {
  state: RoutingState; label: string; reasons: string[]; intake: { vision_problems: boolean; prior_treatment: boolean }
  previous: { case_id: string; created: string; reviewer: string; decision: string; ai_stage: number | null; corrected_stage: number | null; note: string; authenticated: boolean; next_action: NextAction | null } | null
}
export type NextAction = 'urgent_referral' | 'referral' | 'examination' | 'recapture' | 'follow_up' | 'routine_rescreen'
export type Review = {
  id: number; created: string; reviewer: string; decision: 'agree' | 'disagree' | 'ungradable'; corrected_stage: number | null; corrected_dme: string | null
  note: string; ai_stage: number | null; reviewer_user_id: number | null; authenticated: boolean; next_action: NextAction | null; next_action_label: string | null
}
/** Effective (authoritative) state of one eye: the latest signed clinician decision, else the AI output marked provisional. */
export type Effective = {
  case_id: string; eye: Eye; source: 'clinician' | 'ai_provisional'; signed: boolean; pending?: boolean | null; quality_concern: boolean; legacy_reviews: number
  next_action: NextAction | null; next_action_label?: string; stage: number | null; dme: string | null
  decision?: Review['decision']; reviewer?: string; signed_at?: string; note?: string; reanalysed_since_signing?: boolean; newer_photo_case_id?: string
  recapture_fulfilled?: boolean; photos?: number
  ai_at_signing?: { stage: number | null; dme: string | null; route_state: RoutingState | null; model_version: string | null }
}
export type VisitState = 'in_progress' | 'incomplete' | 'quality_check' | 'awaiting_review' | 'decision_recorded'
export type Outcome = {
  state: VisitState; next_action: NextAction | null; next_action_label?: string; missing_eyes: Eye[]; pending_eyes: Eye[]; signed_eyes: Eye[]
  quality_provisional: boolean; complete: boolean; partial: boolean; decided_at: string | null
}
export type RegistrationLink = { ref: string; name: string; camp: { en: string; hi: string }; camp_is_demo: boolean; linked_at: string; linked_by: string; consent_confirmed_at: string }
export type Encounter = {
  id: string; patient_ref: string; created: string; created_by: string | null; eyes: Effective[]; outcome: Outcome; link: RegistrationLink | null
  photos: { id: string; eye: Eye; created: string }[]
}
export type FollowUp = { level: 'routine' | 'refer' | 'urgent' | 'human' | 'retake' | 'incomplete' | 'follow_up' | 'pending'; title: string; text: string }
export type PatientSummary = {
  state: RoutingState; label: string; ai_label: string; notes: string[]; effective: Outcome; encounter_id: string | null; single_photo: boolean
  eyes: { eye: Eye; case_id: string; stage: number | null; label?: string; state: RoutingState; state_label: string; reasons: string[]; defer: boolean; p_referable?: number | null; effective: Effective | null }[]
  follow_up: FollowUp
  note: string
  operating_point: { target: number; wording: string; valid: boolean }
}
export type Queue = 'attention' | 'awaiting' | 'retake' | 'routine' | 'signed'
export type Clinician = { id: number; name: string; role: 'ophthalmologist' }
export type CaseRow = {
  id: string; created: string; patient_ref: string; eye: Eye; status: 'new' | 'reviewed'; source: string; stale: boolean
  assist: Assist; thumbnail: string | null; stage: number | null; stage_label: string | null; dme: 'low' | 'possible' | 'high' | null
  quality_usable: boolean; lesion_regions: number; flags: string[]; routing: Routing
  effective: Effective; queue: Queue; queue_label: string; queue_reason: string; encounter_id: string | null; completeness: { right: boolean; left: boolean } | null
}
export type CaseDetail = Omit<CaseRow, 'thumbnail' | 'stage' | 'stage_label' | 'dme' | 'quality_usable' | 'lesion_regions' | 'flags' | 'queue' | 'queue_label' | 'queue_reason' | 'completeness'> & {
  analysis: Analysis; reviews: Review[]; patient: PatientSummary; routing: Routing; encounter: Encounter | null
}
export type Settings = { target: number; choices: number[]; wording: string; routing_valid: boolean }
export type Disagreement = {
  review_id: number; case_id: string; created: string; reviewer: string; ai_stage: number | null; corrected_stage: number | null
  corrected_dme: string | null; note: string; ai_grader: string | null; patient_ref: string | null; eye: Eye | null; authenticated: boolean; next_action: NextAction | null
}
export type Glossary = Record<string, { plain: string; explain: string; clinical: string }>

/** The pipeline returns bare base64: display images are JPEG, overlays PNG. */
export const jpeg = (b64: string) => (b64.startsWith('data:') ? b64 : `data:image/jpeg;base64,${b64}`)
export const png = (b64: string) => (b64.startsWith('data:') ? b64 : `data:image/png;base64,${b64}`)

/** Error with the HTTP status and the server's machine-readable code (e.g. 'login_required', 'not_clinician'). */
export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string | null = null) { super(message) }
}
/** Fired when the server says the specialist session is missing or expired; App shows the sign-in screen. */
export const AUTH_EVENT = 'drishtiq:auth-required'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  // Same-origin cookies carry the session; the custom header is the CSRF guard every state-changing call needs.
  const headers = new Headers(init?.headers)
  headers.set('X-Requested-With', 'dqn')
  const r = await fetch(url, { credentials: 'same-origin', ...init, headers })
  if (!r.ok) {
    let detail = `Request failed (${r.status})`
    let code: string | null = null
    try {
      const body = await r.json()
      const d = body.detail
      if (typeof d === 'string') detail = d
      else if (Array.isArray(d)) detail = d.map((x: { msg: string }) => x.msg).join('; ')
      else if (d && typeof d === 'object') { detail = d.message ?? detail; code = d.code ?? null }
    } catch {
      /* non-JSON error body */
    }
    if (r.status === 401 || (r.status === 403 && code === 'not_clinician')) window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: { code } }))
    throw new ApiError(detail, r.status, code)
  }
  return r.json()
}
const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  cases: () => request<{ cases: CaseRow[]; calibration: { available: boolean; tau: number | null }; reanalysis: { total: number; done: number } | null }>('/api/cases'),
  case: (id: string) => request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`),
  glossary: () => request<Glossary>('/api/glossary'),
  version: () => request<{ model_version: string; commit: string | null; commit_on_disk: string | null; grader: string; calibrated: boolean }>('/api/version'),
  model: () => request<ModelCard>('/api/model'),
  settings: () => request<Settings>('/api/settings'),
  saveSettings: (target: number) => request<Settings>('/api/settings', json('POST', { target })),
  disagreements: () => request<{ disagreements: Disagreement[]; reviews_total: number }>('/api/disagreements'),
  me: () => request<{ user: Clinician }>('/api/clinician/me'),
  signIn: (identifier: string, password: string) => request<{ user: { name: string } }>('/api/network/auth/login', json('POST', { identifier, password })),
  signOut: () => request<{ ok: boolean }>('/api/network/auth/logout', { method: 'POST' }),
  createEncounter: (patientRef: string, clientKey: string) => request<Encounter>('/api/encounters', json('POST', { patient_ref: patientRef, client_key: clientKey })),
  encounter: (id: string) => request<Encounter>(`/api/encounters/${encodeURIComponent(id)}`),
  link: (id: string, ref: string, code: string, consent: boolean) => request<Encounter>(`/api/encounters/${encodeURIComponent(id)}/link`, json('POST', { ref, code, consent_confirmed: consent })),
  unlink: (id: string, reason: string) => request<Encounter>(`/api/encounters/${encodeURIComponent(id)}/unlink`, json('POST', { reason })),
  createCase: (file: File, patientRef: string, eye: Eye, intake?: { vision_problems: boolean; prior_treatment: boolean }, encounterId?: string) => {
    const body = new FormData()
    body.append('file', file)
    body.append('patient_ref', patientRef)
    body.append('eye', eye)
    if (encounterId) body.append('encounter_id', encounterId)
    if (intake) {
      body.append('vision_problems', String(intake.vision_problems))
      body.append('prior_treatment', String(intake.prior_treatment))
    }
    return request<CaseDetail>('/api/cases', { method: 'POST', body })
  },
  /** Signs a decision as the signed-in clinician (the server takes the identity from the session). */
  review: (id: string, review: { decision: string; corrected_stage: number | null; corrected_dme: string | null; next_action: NextAction | null; note: string }) =>
    request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}/review`, json('POST', review)),
  reportUrl: (patientRef: string, kind: 'doctor' | 'patient', lang: 'en' | 'hi', format: 'html' | 'pdf', caseId?: string | null) =>
    `/api/patients/${encodeURIComponent(patientRef)}/report.${format}?kind=${kind}&lang=${lang}${caseId ? `&case=${encodeURIComponent(caseId)}` : ''}`,
}

export type GradeMetrics = {
  run_id: string; n: number; seconds_per_image: number | null; confusion: number[][]
  point: Record<'qwk' | 'macro_f1' | 'accuracy' | 'recall_g0' | 'recall_g1' | 'recall_g2' | 'recall_g3' | 'recall_g4' | 'severe_under' | 'referable_sens' | 'referable_spec', number>
  ci95: Record<string, [number, number]> | null
}
export type Agreement = {
  run_id: string; source_run: string
  point: Record<'accuracy' | 'within_one' | 'referable_sens' | 'referable_spec', number>
  ci95: Record<'accuracy' | 'within_one' | 'referable_sens' | 'referable_spec', [number, number]>
}
export type SplitCalibration = {
  n: number
  ece_stage_confidence: { before: number; after: number }
  ece_p_referable: { before: number; after: number }
  reliability_p_referable: { bin: number; n: number; mean_predicted: number; observed: number }[]
  abstention: { tau: number; coverage: number; accuracy_retained: number | null; accuracy_deferred: number | null; accuracy_all: number; severe_under_retained: number }
  triage: { auroc: number; referable_in_top20pct: number; workload_to_95pct_sensitivity: number; random_order_workload: number; n: number; referable: number } | null
}
export type ModelCard = {
  version: string
  grader: string
  grader_info: { members: number; description: string; train_data: string; inner_qwk: number | null }
  history: { grader?: string; version?: string; replaced: string; reason: string }[]
  segmenter: Record<LesionKey, { model: string; postprocess: string }>
  grading: { idrid_val: GradeMetrics | null; aptos_val: GradeMetrics | null }
  agreement: { idrid_val: Agreement | null; aptos_val: Agreement | null }
  compared: { model: string; setting: string; decision: string; ref: string; idrid_val: { qwk: number; run_id: string } | null; aptos_val: { qwk: number; run_id: string } | null }[]
  segmentation: Record<string, Record<'idrid_seg_val' | 'ddr_seg_test', Record<string, string> | null>>
  dme_rule: { file: string; min_exudate_area_px: number; val: { n: number; macro_f1: number; high_risk_sensitivity: number; high_risk_ppv: number; no_exudate_specificity: number } }
  calibration: null | { tau: number; fitted_on: string; created: string; inner_holdout: { coverage: number; accuracy_retained: number }; validation: Record<string, SplitCalibration> }
  experiments: { key: string; name: string; question: string; verdict: 'adopt' | 'abandon' | 'not testable' | 'reported'; found: string }[]
  coverage: null | {
    run_ids: string[]; policy: string; target: number; wording: string; valid: boolean; thresholds: Record<string, number>
    sets: Record<string, Record<string, { units: number; referable: number; routed: number; coverage: number; coverage_ci95: [number, number]; missed: number; miss_rate_upper95: number; sensitivity: number; specificity: number }>>
    rule_of_three: Record<string, { referable: number; certifiable_levels: number[] }>
    patient_level: string
  }
  decisions: Record<string, { adr: string; verdict: { passed: boolean }; splits?: Record<string, { delta: { qwk: { point: number; ci95: [number, number] }; severe_under: { point: number; ci95: [number, number] } } }> }>
  checkpoints: Record<string, string>
}
