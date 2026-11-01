import { ArrowRight, CircleCheck, FileText, Link2, PencilLine, ShieldCheck, Unlink } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import tokens from '../../../../design/tokens.json'
import { Alert, Badge, Button, Card, Checkbox, ConfidenceBadge, Field, Input, Segmented, Select, Skeleton, Toast, cn } from '../../design/components'
import { api, type CaseDetail, type Encounter, type Glossary, type LesionKey, type Mode, type NextAction, type Sentence } from '../api'
import { DME_LABEL, NEXT_ACTIONS, ROUTING, VISIT, eyeName, STAGE_CLINICAL, isValidation, nextActionInfo, num, routingAlertTone, validationSource, pct, when } from '../format'
import { linkProps, navigate } from '../router'
import { ImageViewer, type Layer } from './ImageViewer'
import { useUnsavedChanges } from '../useUnsavedChanges'

const LESION_ORDER: LesionKey[] = ['MA', 'HE', 'EX', 'SE']

type Preset = 'original' | 'overlay' | 'cam' | LesionKey

const STAGE_BOX = ['bg-stage-0-tint text-stage-0-text border-stage-0-border', 'bg-stage-1-tint text-stage-1-text border-stage-1-border',
  'bg-stage-2-tint text-stage-2-text border-stage-2-border', 'bg-stage-3-tint text-stage-3-text border-stage-3-border', 'bg-stage-4-tint text-stage-4-text border-stage-4-border']

export function CaseView({ id, glossary, onLoaded }: { id: string; glossary: Glossary | null; onLoaded: (c: CaseDetail) => void }) {
  const [c, setCase] = useState<CaseDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>('simple')
  const [layers, setLayers] = useState<Set<Layer>>(new Set(['MA', 'HE', 'EX', 'SE', 'macula']))
  const [original, setOriginal] = useState(false)
  const [highlight, setHighlight] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [nextId, setNextId] = useState<string | null>(null)

  useEffect(() => {
    setCase(null)
    setError(null)
    let active = true
    api.case(id).then((d) => { if (active) { setCase(d); onLoaded(d) } }, (e) => { if (active) setError(e.message) })
    return () => { active = false }
  }, [id, onLoaded])
  // Next case still waiting for review, in worklist order.
  useEffect(() => {
    let active = true
    api.cases().then((d) => { if (active) setNextId(d.cases.find((x) => x.queue !== 'signed' && x.id !== id)?.id ?? null) }, () => { if (active) setNextId(null) })
    return () => { active = false }
  }, [id, c?.effective.signed])
  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 4000)
    return () => window.clearTimeout(t)
  }, [toast])

  if (error) return <Alert tone="danger" title={`Could not open case ${id}`}>{error}</Alert>
  if (!c) return <CaseSkeleton />

  const a = c.analysis
  const ok = a.status === 'ok' && a.grading && a.findings
  const toggle = (l: Layer) => { setHighlight(null); setOriginal(false); setLayers((s) => { const n = new Set(s); n.delete('cam'); if (n.has(l)) n.delete(l); else n.add(l); return n }) }
  const stagePlain = (g: number) => glossary?.[`stage${g}`]?.plain ?? STAGE_CLINICAL[g]
  const stageName = (g: number) => (mode === 'simple' ? stagePlain(g) : STAGE_CLINICAL[g])
  const lesionName = (k: LesionKey) => (mode === 'simple' ? glossary?.[k]?.plain : glossary?.[k]?.clinical) ?? a.findings?.lesions[k].name ?? k

  function applyPreset(p: Preset) {
    setHighlight(null)
    if (p === 'original') { setOriginal(true); return }
    setOriginal(false)
    setLayers(new Set<Layer>(p === 'overlay' ? [...LESION_ORDER, 'macula'] : p === 'cam' ? ['cam'] : [p, 'macula']))
  }
  // Explanation sentence click: show only the lesions (and landmarks) the sentence is about.
  function focusSentence(s: Sentence) {
    if (highlight === s.id) { setHighlight(null); applyPreset('overlay'); return }
    const refs = s.refs?.lesions ?? []
    const marks = (s.refs?.landmarks ?? []).filter((m): m is 'macula' | 'disc' => m === 'macula' || m === 'disc')
    setOriginal(false)
    setLayers(new Set<Layer>([...refs, ...(marks.length ? marks : ['macula' as const])]))
    setHighlight(s.id)
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title flex flex-wrap items-center gap-3">
            {c.patient_ref} · {eyeName(c.eye)}
            <span className="flex flex-wrap items-center gap-2 font-sans">
              {a.status === 'ok' ? <Badge tone="brand" dot>Analysis complete</Badge> : <Badge tone="danger" dot>Not gradable</Badge>}
              {isValidation(c.source) && <Badge tone="info">Validation image</Badge>}
              {c.effective.signed ? <Badge tone="success" icon={ShieldCheck}>Signed: {nextActionInfo(c.effective.next_action)?.label}</Badge> : <Badge tone="neutral">Not yet signed</Badge>}
            </span>
          </h1>
          <div className="mt-3"><Badge tone={ROUTING[c.routing.state].tone} dot>AI-suggested: {c.routing.label}</Badge></div>
          <p className="mt-2 text-secondary text-text-secondary">Case {c.id} · Added {when(c.created)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented label="Explanation level" value={mode} onChange={setMode} options={[{ value: 'simple', label: 'Simple' }, { value: 'clinical', label: 'Clinical' }]} />
          <Button variant="secondary" icon={FileText} onClick={() => navigate(`/patients/${encodeURIComponent(c.patient_ref)}/report?case=${c.id}`)}>Report</Button>
          <Button variant="secondary" onClick={() => nextId && navigate(`/cases/${nextId}`)} state={nextId ? 'default' : 'disabled'}
            title={nextId ? `Open ${nextId}, the next case waiting for review` : 'No other case is waiting for review'}>
            Next case<ArrowRight size={16} strokeWidth={1.75} aria-hidden />
          </Button>
        </div>
      </div>

      <VisitStrip c={c} onChange={(e) => setCase({ ...c, encounter: e })} />

      <div className="case-layout">
        <div className="min-w-0 [grid-area:viewer]">
          <ImageViewer analysis={a} eye={eyeName(c.eye)} layers={layers} original={original}
            onOriginal={() => applyPreset('original')} onMode={m => applyPreset(m === 'lesions' ? 'overlay' : 'cam')}
            onToggle={toggle} name={lesionName} />
        </div>
        <div className="flex min-w-0 flex-col gap-6 [grid-area:support]">
          <PatientCard c={c} stageName={stageName} />
          {ok && (
            <Card title="Explanation" subtitle="Click a sentence to show the lesions it is about.">
              <ExplanationList sentences={a.explanations ?? []} mode={mode} active={highlight} onPick={focusSentence} />
            </Card>
          )}
        </div>

        {/* Assessment panel */}
        <div className="flex min-w-0 flex-col gap-4 [grid-area:assessment]">
          {isValidation(c.source) && (
            <Alert tone="info" title="Validation image, not used for training">
              {validationSource(c.source).dataset} image {validationSource(c.source).id}. Shown as the model sees any new image; its specialist grade is in the validation set.
            </Alert>
          )}
          {c.stale && <Alert tone="info" title="Analysed with earlier models">This case is being re-analysed with the current models. Reload in a minute.</Alert>}
          {a.status === 'rejected' && (
            <Alert tone="danger" title="Not a gradable fundus photograph">{a.quality.issues.join(' ') || 'No retinal field was detected.'} Retake the photograph.</Alert>
          )}
          {a.status === 'ok' && !a.quality.usable && (
            <Alert tone="warning" title="Low image quality">{a.quality.issues.join(' ')} Small lesions may be missed; consider retaking the photograph.</Alert>
          )}
          {ok && !c.assist.available && a.grading!.low_confidence && (
            <Alert tone="warning" title="Low confidence: a doctor should grade this image">
              The grade score lies close to a stage boundary. Calibrated confidence will appear once the calibration job has run for this grader.
            </Alert>
          )}
          {ok && c.assist.defer && c.assist.reason === 'low confidence' && (
            <Alert tone="warning" title="The AI defers to a human grader">
              Its confidence in this stage ({pct(c.assist.stage_confidence)}) is below the deferral threshold ({pct(c.assist.tau)}). Grade this image yourself.
            </Alert>
          )}

          {ok && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-secondary font-medium text-text-secondary">AI severity suggestion <span className="text-text-muted">(provisional)</span></p>
                {c.assist.confidence_level ? <ConfidenceBadge level={c.assist.confidence_level} /> : <Badge>Confidence not calibrated</Badge>}
              </div>
              <div className={cn('mt-3 inline-flex flex-col rounded-card border px-4 py-3', STAGE_BOX[a.grading!.grade])}>
                <span className="font-display text-display-sm leading-none">Stage {a.grading!.grade}</span>
                <span className="mt-1 text-secondary font-medium">{STAGE_CLINICAL[a.grading!.grade]}</span>
              </div>
              {mode === 'simple' && <p className="mt-2 text-body text-text-secondary">{stagePlain(a.grading!.grade)}</p>}
              {!a.quality.usable && <p className="mt-2 rounded-control bg-status-warning-tint p-2 text-caption text-status-warning-text">The image failed the automated quality check, so this stage is not reliable. It must never be read as the eye being free of disease.</p>}
              <dl className="mt-4 flex flex-col divide-y divide-border-default border-t border-border-default text-body">
                {[
                  [mode === 'simple' ? 'Chance it needs an eye specialist' : 'P(referable DR), calibrated', c.assist.available ? pct(c.assist.p_referable) : '—'],
                  [mode === 'simple' ? 'Confidence in this stage' : 'Stage confidence (calibrated)', c.assist.available ? pct(c.assist.stage_confidence) : '—'],
                  [mode === 'simple' ? 'Swelling risk at the centre of vision' : 'Macular-edema risk', DME_LABEL[a.findings!.macular_edema_risk.level]],
                  ...(mode === 'clinical' ? [['Grade score (regression)', num(a.grading!.score)]] : []),
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-4 py-2">
                    <dt className="text-text-secondary">{k}</dt>
                    <dd className="font-semibold tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}

          {ok && (
            <Card title="Clinician decision" subtitle="Your signed decision governs this eye's next action, the report and the patient's status.">
              <DecisionNow c={c} />
              <ReviewForm key={c.id} c={c} onSaved={(d) => { setCase(d); setToast('Decision signed. Specialist Attention, the report and the patient status now follow it.') }} />
              <Button variant="secondary" icon={FileText} className="mt-4 w-full"
                onClick={() => navigate(`/patients/${encodeURIComponent(c.patient_ref)}/report?case=${c.id}`)}>View report</Button>
            </Card>
          )}
          {!ok && (
            <Card title="Clinician decision" subtitle="The AI could not grade this photograph. You can still record what you see, or request a retake.">
              <DecisionNow c={c} />
              <ReviewForm key={c.id} c={c} onSaved={(d) => { setCase(d); setToast('Decision signed.') }} />
            </Card>
          )}

          <RoutingCard c={c} />

          {ok && (
            <Card title="Candidate lesion regions (AI)" subtitle="Segmentation model output: candidate regions, not confirmed lesions. A separate model from the severity grader.">
              <FindingsList c={c} mode={mode} name={lesionName} layers={layers} toggle={toggle} />
            </Card>
          )}


        </div>
      </div>
      {toast && <div className="fixed bottom-4 right-4 z-30"><Toast title={toast} /></div>}
    </>
  )
}

function FindingsList({ c, mode, name, layers, toggle }: { c: CaseDetail; mode: Mode; name: (k: LesionKey) => string; layers: Set<Layer>; toggle: (l: Layer) => void }) {
  const f = c.analysis.findings!
  const dme = f.macular_edema_risk
  return (
    <div className="flex flex-col gap-4">
      <table className="w-full text-body">
        <caption className="sr-only">Predicted lesion regions</caption>
        <thead>
          <tr className="border-b border-border-default text-caption text-text-secondary">
            <th scope="col" className="pb-2 text-left font-medium">{mode === 'simple' ? 'Predicted regions' : 'Lesion (overlay)'}</th>
            <th scope="col" className="pb-2 text-right font-medium">Regions</th>
            <th scope="col" className="pb-2 text-right font-medium">{mode === 'simple' ? 'Areas' : 'Quadrants'}</th>
          </tr>
        </thead>
        <tbody>
          {LESION_ORDER.map((k) => {
            const l = f.lesions[k]
            const quads = Object.values(l.per_quadrant).filter((n) => n > 0).length
            return (
              <tr key={k} className="border-b border-border-default last:border-0">
                <td className="py-2"><Checkbox checked={layers.has(k)} swatch={tokens.color.lesion[k]} label={name(k)} onChange={() => toggle(k)} /></td>
                <td className="py-2 text-right font-semibold">{l.count}</td>
                <td className="py-2 text-right text-text-secondary">{quads} of 4</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="rounded-control bg-surface-subtle p-3">
        <p className="text-secondary font-medium">{mode === 'simple' ? 'Swelling risk at the centre of vision' : 'Macular-edema risk (photographic)'}: {DME_LABEL[dme.level]}</p>
        <p className="mt-1 text-caption text-text-secondary">
          {dme.nearest_exudate_dd == null
            ? (mode === 'simple' ? 'No yellow deposits were found.' : 'No hard exudates segmented.')
            : mode === 'simple'
              ? `The nearest yellow deposit is ${dme.nearest_exudate_dd.toFixed(1)} optic-nerve widths from the centre of vision.`
              : `Nearest hard exudate ${dme.nearest_exudate_dd.toFixed(1)} DD from the fovea; ${dme.exudates_within_1dd} within 1 DD.`}
          {dme.landmarks_uncertain && ' The centre of vision could not be located with certainty (dashed ring).'}
        </p>
      </div>
      {c.analysis.consistency_flags && c.analysis.consistency_flags.length > 0 && (
        <p className="text-caption text-text-secondary">Checks raised: {c.analysis.consistency_flags.join(', ')}. See the explanation below.</p>
      )}
    </div>
  )
}

const SECTION_TITLE: Record<Sentence['section'], string> = {
  summary: 'Summary', evidence: 'Evidence', reasoning: 'Why this stage', macula: 'Centre of vision', limits: 'Limits', flags: 'Checks',
}

function ExplanationList({ sentences, mode, active, onPick }: { sentences: Sentence[]; mode: Mode; active: string | null; onPick: (s: Sentence) => void }) {
  const sections = (Object.keys(SECTION_TITLE) as Sentence['section'][]).map((s) => [s, sentences.filter((x) => x.section === s)] as const).filter(([, xs]) => xs.length)
  return (
    <div className="flex flex-col gap-4">
      {sections.map(([s, xs]) => (
        <section key={s}>
          <h3 className="text-secondary font-semibold text-text-secondary">{SECTION_TITLE[s]}</h3>
          <ul className="mt-1 flex flex-col gap-1 text-body">
            {xs.map((x) => {
              const text = mode === 'simple' ? x.simple : x.clinical
              return (
                <li key={x.id}>
                  {x.refs?.lesions?.length ? (
                    <button aria-pressed={active === x.id} onClick={() => onPick(x)}
                      className={cn('w-full rounded-control px-2 py-1 text-left', active === x.id ? 'bg-brand-50 text-brand-800' : 'hover:bg-brand-50')}>
                      {text}
                    </button>
                  ) : <span className="block px-2 py-1">{text}</span>}
                </li>
              )
            })}
          </ul>
        </section>
      ))}
      <p className="text-caption text-text-muted">Every number in these sentences is taken from the findings record; nothing is generated freely.</p>
    </div>
  )
}

export function ReviewForm({ c, onSaved }: { c: Pick<CaseDetail, 'id' | 'analysis' | 'reviews'>; onSaved: (c: CaseDetail) => void }) {
  const [dirty, setDirty] = useState(false)
  useUnsavedChanges(dirty, 'This clinician review has unsaved changes. Leave this case?')
  const gradable = c.analysis.status === 'ok' && !!c.analysis.grading
  // Safe default: when the automated quality check failed, start from 'ungradable' (which can never be signed as routine).
  const [decision, setDecision] = useState<'agree' | 'disagree' | 'ungradable'>(gradable && c.analysis.quality.usable ? 'agree' : 'ungradable')
  const [stage, setStage] = useState('')
  const [dme, setDme] = useState('')
  const [action, setAction] = useState<NextAction | ''>('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [touched, setTouched] = useState(false)
  const stageError = touched && decision === 'disagree' && stage === '' ? 'Choose the stage you would give.' : undefined
  const decidedStage = decision === 'disagree' ? (stage === '' ? null : Number(stage)) : decision === 'agree' ? c.analysis.grading?.grade ?? null : null
  const decidedDme = dme || (decision === 'agree' ? c.analysis.findings?.macular_edema_risk.level ?? null : null)
  const needsNote = action === 'routine_rescreen' && decision !== 'ungradable' && ((decidedStage ?? 0) >= 2 || decidedDme === 'high')
  const actionError = touched && !action ? 'Choose the next action.' : touched && decision === 'ungradable' && action === 'routine_rescreen'
    ? 'An image that cannot be assessed must not be signed as routine: choose a retake or an examination.' : undefined
  const noteError = touched && needsNote && note.trim().length < 5 ? 'Explain why routine rescreening fits this stage or macular finding.' : undefined

  async function save() {
    if (busy) return
    setTouched(true)
    const bad = (decision === 'disagree' && stage === '') ? 'stage' : !action || (decision === 'ungradable' && action === 'routine_rescreen') ? 'action-urgent_referral' : needsNote && note.trim().length < 5 ? 'note' : null
    if (bad) { document.getElementById(bad)?.focus(); return }
    setBusy(true)
    setError(null)
    try {
      const saved = await api.review(c.id, { decision, corrected_stage: decision === 'disagree' ? Number(stage) : null, corrected_dme: decision === 'ungradable' ? null : dme || null, next_action: action || null, note })
      setDirty(false)
      onSaved(saved)
      setNote(''); setAction('')
      setTouched(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Alert tone="danger" title="Decision not signed">{error}</Alert>}
      <fieldset disabled={busy} className="contents" onChange={() => setDirty(true)}>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1 2xl:grid-cols-2">
        <Button variant={decision === 'agree' ? 'primary' : 'secondary'} icon={CircleCheck} aria-pressed={decision === 'agree'} disabled={!gradable} title={gradable ? undefined : 'The AI gave no stage to confirm'} onClick={() => { setDecision('agree'); setDirty(true) }}>Confirm AI stage</Button>
        <Button variant={decision === 'disagree' ? 'primary' : 'secondary'} icon={PencilLine} aria-pressed={decision === 'disagree'} onClick={() => { setDecision('disagree'); setDirty(true) }}>Change stage</Button>
      </div>
      <button type="button" onClick={() => { setDecision('ungradable'); setDirty(true) }} aria-pressed={decision === 'ungradable'}
        className={cn('self-start text-secondary underline underline-offset-2', decision === 'ungradable' ? 'font-semibold text-brand-800' : 'text-text-secondary hover:text-text-primary')}>
        Mark the image ungradable instead
      </button>
      {decision === 'disagree' && (
        <Field id="stage" label="Stage you would give" error={stageError}>
          <Select id="stage" value={stage} onChange={(e) => setStage(e.target.value)}>
            <option value="">Choose a stage</option>
            {STAGE_CLINICAL.map((s, i) => <option key={i} value={i}>Stage {i} · {s}</option>)}
          </Select>
        </Field>
      )}
      {decision !== 'ungradable' && <Field id="dme" label="Macular-edema risk (optional)">
        <Select id="dme" value={dme} onChange={(e) => setDme(e.target.value)}>
          <option value="">Not assessed</option>
          <option value="low">Low</option><option value="possible">Possible</option><option value="high">High</option>
        </Select>
      </Field>}
      <fieldset className="flex flex-col gap-2" aria-describedby={actionError ? 'action-error' : undefined}>
        <legend className="mb-1 text-secondary font-medium">Next action for this eye</legend>
        {NEXT_ACTIONS.map((n) => (
          <label key={n.value} className={cn('flex min-h-[44px] cursor-pointer items-start gap-3 rounded-control border px-3 py-2', action === n.value ? 'border-brand-600 bg-brand-50' : 'border-border-default hover:bg-surface-subtle',
            decision === 'ungradable' && n.value === 'routine_rescreen' && 'opacity-50')}>
            <input id={`action-${n.value}`} type="radio" name={`action-${c.id}`} value={n.value} checked={action === n.value} className="mt-1"
              disabled={decision === 'ungradable' && n.value === 'routine_rescreen'} onChange={() => { setAction(n.value); setDirty(true) }} />
            <span className="flex flex-col"><span className="text-body font-medium">{n.label}</span><span className="text-caption text-text-secondary">{n.hint}</span></span>
          </label>
        ))}
        {actionError && <p id="action-error" className="text-caption text-status-danger-text">{actionError}</p>}
      </fieldset>
      <Field id="note" label={needsNote ? 'Justification (required for this combination)' : 'Note (optional)'} error={noteError}>
        <textarea id="note" value={note} maxLength={1000} rows={3} onChange={(e) => setNote(e.target.value)} aria-invalid={!!noteError}
          className="w-full rounded-control border border-border-strong bg-surface-card px-3 py-2 text-body text-text-primary hover:border-neutral-400" />
      </Field>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-caption text-text-muted">Signed under your account. Earlier decisions are kept; a new one replaces them.</p>
        <Button onClick={save} state={busy ? 'loading' : 'default'} icon={ShieldCheck}>Sign decision</Button>
      </div>
      </fieldset>
      {c.reviews.length > 0 && (
        <div className="border-t border-border-default pt-4">
          <h3 className="text-secondary font-semibold text-text-secondary">Decision history</h3>
          <ul className="mt-2 flex flex-col gap-2">
            {c.reviews.map((r) => (
              <li key={r.id} className="text-secondary">
                {r.authenticated ? <Badge tone="success" icon={ShieldCheck}>Signed</Badge> : <Badge tone="neutral">Historical, not authenticated</Badge>}{' '}
                <span className="font-medium">{r.reviewer}</span> · {when(r.created)} · {r.decision === 'disagree' ? `Stage ${r.corrected_stage} (AI ${r.ai_stage ?? '—'})` : r.decision === 'agree' ? `Confirmed AI stage ${r.ai_stage ?? '—'}` : 'Ungradable'}
                {r.next_action_label && <span> · <b>{r.next_action_label}</b></span>}
                {r.note && <span className="text-text-secondary"> · {r.note}</span>}
              </li>
            ))}
          </ul>
          {c.reviews.some((r) => !r.authenticated) && <p className="mt-2 text-caption text-text-muted">Historical reviews were recorded before signed accounts existed. They are kept for the record but do not set the next action.</p>}
        </div>
      )}
    </div>
  )
}

function RoutingCard({ c }: { c: CaseDetail }) {
  const r = c.routing
  return (
    <Card title="AI-suggested routing (provisional)" subtitle="Orders Specialist Attention. It is not a clinical decision.">
      <div className="mb-3"><Badge tone={ROUTING[r.state].tone} dot>{r.label}</Badge></div>
      <Alert tone={routingAlertTone(r.state)} title={r.state === 'ROUTINE_RESCREEN_ELIGIBLE' ? 'Why it is eligible' : 'Why it needs attention'}>
        <ul className="flex list-disc flex-col gap-1 pl-4">{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
        {r.previous && (
          <p className="mt-2">Previous visit ({r.previous.case_id}, {r.previous.created.slice(0, 10)}): {r.previous.authenticated ? 'signed' : 'historical review'} by {r.previous.reviewer},{' '}
            {r.previous.decision === 'disagree' ? `stage ${r.previous.corrected_stage}` : r.previous.decision === 'agree' ? `agreed with AI stage ${r.previous.ai_stage}` : 'ungradable'}
            {r.previous.note && ` · "${r.previous.note}"`}</p>
        )}
        {(r.intake.vision_problems || r.intake.prior_treatment) && (
          <p className="mt-2">Intake: {[r.intake.vision_problems && 'reports vision problems', r.intake.prior_treatment && 'previous eye treatment / laser'].filter(Boolean).join('; ')}.</p>
        )}
      </Alert>
      <p className="mt-3 text-caption text-text-muted">Operating point: {c.patient.operating_point.wording}.</p>
    </Card>
  )
}

function PatientCard({ c, stageName }: { c: CaseDetail; stageName: (g: number) => string }) {
  const p = c.patient
  return (
    <Card title={`Patient ${c.patient_ref}`} subtitle={p.single_photo ? 'Single photograph (no visit pairing recorded)' : 'This visit: latest photograph of each eye'}
      actions={<a {...linkProps(`/patients/${encodeURIComponent(c.patient_ref)}/report?case=${c.id}`)} className="text-secondary font-medium text-text-link">Open report</a>}>
      <div className="flex flex-col gap-3">
        {p.eyes.map((e) => (
          <Row key={e.case_id} current={e.case_id === c.id}>
            <span>{eyeName(e.eye)} {e.case_id !== c.id && <a {...linkProps(`/cases/${e.case_id}`)} className="text-text-link">({e.case_id})</a>}</span>
            <span className="flex flex-wrap items-center justify-end gap-2 text-right">
              {e.effective?.signed ? <Badge tone={nextActionInfo(e.effective.next_action)?.tone ?? 'neutral'} icon={ShieldCheck}>{nextActionInfo(e.effective.next_action)?.label}</Badge> : <Badge tone="neutral">Not signed</Badge>}
              <span className="text-caption text-text-muted">AI: {e.stage == null ? 'not assessable' : `stage ${e.stage} · ${stageName(e.stage)}`}</span>
            </span>
          </Row>
        ))}
        <Alert tone={p.effective.state === 'decision_recorded' && ['urgent_referral', 'referral', 'examination'].includes(p.effective.next_action ?? '') ? 'danger' : p.effective.state === 'decision_recorded' ? 'success' : 'info'}
          title={p.effective.state === 'decision_recorded' ? `Visit next action: ${p.effective.next_action_label}` : VISIT[p.effective.state].label}>
          {p.effective.missing_eyes.length > 0 && <p>No {p.effective.missing_eyes.join(' or ')}-eye photograph in this visit: screening incomplete.</p>}
          {p.effective.state === 'decision_recorded' && p.effective.pending_eyes.length > 0 && <p>Still awaiting your review: {p.effective.pending_eyes.join(', ')} eye.</p>}
          {p.effective.state !== 'decision_recorded' && p.effective.partial && <p>Routine rescreening needs both eyes photographed and signed.</p>}
          <p className="mt-1 text-caption">{p.ai_label}. {p.note}</p>
        </Alert>
      </div>
    </Card>
  )
}

function Row({ children, current }: { children: ReactNode; current: boolean }) {
  return <div className={cn('flex flex-wrap items-center justify-between gap-3 text-body', current && 'font-medium')}>{children}</div>
}

function CaseSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_380px]">
      <Skeleton className="h-[560px] w-full" />
      <div className="flex flex-col gap-4"><Skeleton className="h-[160px] w-full" /><Skeleton className="h-[320px] w-full" /></div>
    </div>
  )
}

/** The current authoritative state of this eye, above the decision form. */
function DecisionNow({ c }: { c: CaseDetail }) {
  const e = c.effective
  if (!e.signed) {
    return <div className="mb-4 rounded-control border border-dashed border-border-strong p-3 text-secondary text-text-secondary">
      <b className="text-text-primary">No signed decision for this photograph.</b> The AI suggestion above is provisional{e.legacy_reviews ? '; a historical review exists but was not made under a signed account' : ''}.
    </div>
  }
  return <div className="mb-4 rounded-control border border-status-success-border bg-status-success-tint p-3 text-secondary">
    <p className="flex flex-wrap items-center gap-2"><ShieldCheck size={16} aria-hidden /><b>{e.next_action_label}</b>{e.stage != null && <span>· Stage {e.stage} · {STAGE_CLINICAL[e.stage]}</span>}</p>
    <p className="mt-1 text-caption">Signed by {e.reviewer} · {e.signed_at ? when(e.signed_at) : ''}. AI at signing: stage {e.ai_at_signing?.stage ?? '—'}.</p>
    {e.reanalysed_since_signing && <p className="mt-1 text-caption">The AI has been re-analysed since you signed. Your decision stands; sign again if you want to change it.</p>}
  </div>
}

/** Right / left eye of this visit (encounter), the visit outcome, and the camp-registration link. */
function VisitStrip({ c, onChange }: { c: CaseDetail; onChange: (e: Encounter) => void }) {
  const e = c.encounter
  if (!e) {
    return <div className="mb-6"><Alert tone="info" title="Single photograph">This case was recorded before visits paired both eyes. It is not combined with any other photograph.</Alert></div>
  }
  const byEye = (eye: 'right' | 'left') => e.eyes.find((x) => x.eye === eye)
  const latestPhoto = (eye: 'right' | 'left') => e.photos.find((p) => p.eye === eye)
  return (
    <section aria-label="This visit" className="mb-6 grid gap-3 rounded-card border border-border-default bg-surface-card p-4 shadow-card lg:grid-cols-[1fr_1fr_1.4fr]">
      {(['right', 'left'] as const).map((eye) => {
        const x = byEye(eye), photo = latestPhoto(eye)
        return <div key={eye} className={cn('rounded-control border p-3', photo ? 'border-border-default' : 'border-status-warning-border bg-status-warning-tint')}>
          <p className="text-caption font-medium uppercase tracking-wide text-text-secondary">{eye === 'right' ? 'Right eye (OD)' : 'Left eye (OS)'}</p>
          {photo ? <>
            <p className="mt-1 text-body font-semibold">Captured{photo.id === c.id ? ' · this photo' : ''}</p>
            <p className="text-caption text-text-secondary">{x?.signed ? `Signed: ${x.next_action_label}` : 'Not yet signed'}{x?.pending && x.signed ? ' · newer photo awaiting review' : ''}{x?.quality_concern && !x.signed ? ' · image quality flagged (provisional)' : ''}</p>
            {photo.id !== c.id && <a {...linkProps(`/cases/${photo.id}`)} className="mt-1 inline-block text-caption font-medium text-text-link">Open {photo.id}</a>}
          </> : <>
            <p className="mt-1 text-body font-semibold text-status-warning-text">Missing</p>
            <p className="text-caption text-status-warning-text">Screening incomplete. Add this eye from New screening with the same visit.</p>
          </>}
        </div>
      })}
      <div className="flex flex-col gap-2 rounded-control border border-border-default p-3">
        <p className="text-caption font-medium uppercase tracking-wide text-text-secondary">Visit {e.id}</p>
        <p className="text-body font-semibold">{e.outcome.state === 'decision_recorded' ? e.outcome.next_action_label : VISIT[e.outcome.state].label}</p>
        <RegistrationLink e={e} onChange={onChange} />
      </div>
    </section>
  )
}

function RegistrationLink({ e, onChange }: { e: Encounter; onChange: (e: Encounter) => void }) {
  const [open, setOpen] = useState(false)
  const [ref, setRef] = useState('')
  const [code, setCode] = useState('')
  const [consent, setConsent] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function run(f: () => Promise<Encounter>) {
    setBusy(true); setError(null)
    try { onChange(await f()); setOpen(false); setRef(''); setCode(''); setConsent(false); setReason('') } catch (x) { setError((x as Error).message) } finally { setBusy(false) }
  }
  if (e.link) {
    return <div className="text-caption text-text-secondary">
      <p className="flex items-center gap-2 text-secondary text-text-primary"><Link2 size={15} aria-hidden />Linked to camp registration <b>{e.link.ref}</b></p>
      <p>{e.link.name} · {e.link.camp.en}{e.link.camp_is_demo ? ' (demonstration camp)' : ''} · linked by {e.link.linked_by}, {when(e.link.linked_at)}</p>
      <p>The patient sees only the visit status and the next action you sign, on their receipt's status page.</p>
      {!open ? <Button compact variant="ghost" icon={Unlink} onClick={() => setOpen(true)} className="mt-1">Unlink</Button> : <div className="mt-2 flex flex-col gap-2">
        {error && <Alert tone="danger" title="Not unlinked">{error}</Alert>}
        <Field id={`unlink-${e.id}`} label="Reason (recorded)"><Input id={`unlink-${e.id}`} value={reason} onChange={(x) => setReason(x.target.value)} maxLength={200} /></Field>
        <div className="flex gap-2"><Button compact variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button compact state={busy ? 'loading' : reason.trim().length >= 3 ? 'default' : 'disabled'} onClick={() => run(() => api.unlink(e.id, reason.trim()))}>Unlink</Button></div>
      </div>}
    </div>
  }
  if (!open) return <Button compact variant="secondary" icon={Link2} onClick={() => setOpen(true)}>Link camp registration</Button>
  return <form className="flex flex-col gap-2" onSubmit={(x) => { x.preventDefault(); if (ref.trim() && code.trim() && consent) void run(() => api.link(e.id, ref.trim(), code.trim(), consent)) }}>
    <p className="text-caption text-text-secondary">Enter the reference and code from the receipt the patient shows you. Records are never matched by name, phone or PIN.</p>
    {error && <Alert tone="danger" title="Not linked">{error}</Alert>}
    <div className="grid grid-cols-2 gap-2">
      <Field id={`ref-${e.id}`} label="Reference"><Input id={`ref-${e.id}`} value={ref} onChange={(x) => setRef(x.target.value.toUpperCase())} placeholder="DQN-XXXXXX" maxLength={20} /></Field>
      <Field id={`code-${e.id}`} label="Code"><Input id={`code-${e.id}`} value={code} onChange={(x) => setCode(x.target.value.toUpperCase())} placeholder="XXXX-XXXX" maxLength={20} /></Field>
    </div>
    <Checkbox checked={consent} onChange={setConsent} label="The person agreed to link this screening to their registration." />
    <div className="flex gap-2"><Button compact variant="secondary" type="button" onClick={() => setOpen(false)}>Cancel</Button><Button compact type="submit" state={busy ? 'loading' : ref.trim() && code.trim() && consent ? 'default' : 'disabled'}>Link</Button></div>
  </form>
}
