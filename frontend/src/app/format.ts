import type { Assist, Eye, NextAction, Queue, RoutingState, VisitState } from './api'

/** Next actions a clinician signs, most urgent first (same order and wording as backend/clinical_state.py). */
export const NEXT_ACTIONS: { value: NextAction; label: string; hint: string; tone: 'danger' | 'orange' | 'warning' | 'info' | 'slate' }[] = [
  { value: 'urgent_referral', label: 'Urgent referral', hint: 'See an eye specialist as soon as possible', tone: 'danger' },
  { value: 'referral', label: 'Referral', hint: 'Book a visit with an eye specialist', tone: 'orange' },
  { value: 'examination', label: 'In-person examination', hint: 'Cannot be assessed from the photograph', tone: 'orange' },
  { value: 'recapture', label: 'Retake photograph', hint: 'The photograph must be taken again', tone: 'info' },
  { value: 'follow_up', label: 'Follow-up', hint: 'Follow-up with the eye-care team', tone: 'warning' },
  { value: 'routine_rescreen', label: 'Routine rescreening', hint: 'Next routine screening', tone: 'slate' },
]
export const nextActionInfo = (a: NextAction | null | undefined) => NEXT_ACTIONS.find((x) => x.value === a)

/** Visit (encounter) states before and after sign-off. Objective process facts only until a clinician signs. */
export const VISIT: Record<VisitState, { label: string; tone: 'danger' | 'warning' | 'info' | 'slate' | 'success' }> = {
  in_progress: { label: 'Screening in progress', tone: 'info' },
  incomplete: { label: 'Screening incomplete', tone: 'warning' },
  quality_check: { label: 'Image quality to be checked (automated, provisional)', tone: 'warning' },
  awaiting_review: { label: 'Awaiting clinician review', tone: 'info' },
  decision_recorded: { label: 'Clinician decision recorded', tone: 'success' },
}

/** Specialist Attention queues. */
export const QUEUES: { value: Queue | 'all'; label: string }[] = [
  { value: 'attention', label: 'Needs attention' },
  { value: 'awaiting', label: 'Awaiting review' },
  { value: 'retake', label: 'Retake / cannot assess' },
  { value: 'routine', label: 'Routine' },
  { value: 'signed', label: 'Signed' },
  { value: 'all', label: 'All' },
]
/** Older links used ?tab=review / ?tab=reviewed. */
export const queueFromTab = (tab: string | null | undefined): Queue | 'all' =>
  tab === 'review' ? 'attention' : tab === 'reviewed' ? 'signed' : (QUEUES.find((q) => q.value === tab)?.value ?? 'attention')

export const STAGE_CLINICAL = ['No apparent DR', 'Mild NPDR', 'Moderate NPDR', 'Severe NPDR', 'Proliferative DR']
export const EYE_LABEL: Record<Eye, string> = { right: 'Right', left: 'Left', unknown: 'Not recorded' }
/** "Right eye", "Left eye", "Eye not recorded" (never "Not recorded eye"). */
export const eyeName = (e: Eye) => (e === 'unknown' ? 'Eye not recorded' : `${EYE_LABEL[e]} eye`)
export const DME_LABEL = { low: 'Low', possible: 'Possible', high: 'High' } as const

export const pct = (v: number | null | undefined, digits = 0) => (v == null ? '—' : `${(100 * v).toFixed(digits)}%`)
export const num = (v: number | null | undefined, digits = 2) => (v == null ? '—' : v.toFixed(digits))

export function when(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** Plain reason a case sits where it does in the worklist (ADR-020 order); superseded by ROUTING (ADR-040). */
export function triageReason(a: Assist, usable: boolean): { tone: 'danger' | 'warning' | 'info' | 'neutral'; label: string } {
  if (!usable) return { tone: 'warning', label: 'Image quality' }
  if (a.defer) return { tone: 'warning', label: 'AI defers' }
  if (a.available && (a.p_referable ?? 0) >= 0.5) return { tone: 'danger', label: 'Referable likely' }
  if (a.available) return { tone: 'neutral', label: 'Referable unlikely' }
  return { tone: 'neutral', label: 'Awaiting calibration' }
}

/** Validation images (IDRiD-val, APTOS-val) shown as example cases; the models never trained on them. */
export const isValidation = (source: string) => source.startsWith('validation:')
/** Specialist grade is not stored with the case; the dataset name and image ID are, for traceability. */
export const validationSource = (source: string) => {
  const [, split, id] = source.split(':')
  return { dataset: split === 'aptos_val' ? 'APTOS-val' : 'IDRiD-val', id }
}

/** Routing states (ADR-040): tone by severity. Routine is neutral, never green: green would read as an all-clear the AI does not give. */
export const ROUTING: Record<RoutingState, { label: string; tone: 'danger' | 'warning' | 'orange' | 'info' | 'slate' }> = {
  URGENT_REVIEW: { label: 'Expedited review', tone: 'danger' },
  CLINICIAN_REVIEW: { label: 'Clinician review', tone: 'warning' },
  REFERABLE: { label: 'Referable', tone: 'orange' },
  RETAKE: { label: 'Retake photo', tone: 'info' },
  INCOMPLETE_SCREENING: { label: 'Incomplete', tone: 'info' },
  ROUTINE_RESCREEN_ELIGIBLE: { label: 'Routine rescreening', tone: 'slate' },
}

/** Alert tone for a routing state (alerts have no orange / slate variant). */
export const routingAlertTone = (s: RoutingState): 'danger' | 'warning' | 'info' =>
  ({ danger: 'danger', warning: 'warning', orange: 'warning', info: 'info', slate: 'info' } as const)[ROUTING[s].tone]
