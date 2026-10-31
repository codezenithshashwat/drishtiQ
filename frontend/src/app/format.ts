import type { Assist, Eye, RoutingState } from './api'

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
