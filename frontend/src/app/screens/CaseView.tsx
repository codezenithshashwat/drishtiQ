import { ArrowRight, CircleCheck, FileText, PencilLine } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import tokens from '../../../../design/tokens.json'
import { Alert, Badge, Button, Card, Checkbox, ConfidenceBadge, Field, Input, Segmented, Select, Skeleton, Toast, cn } from '../../design/components'
import { api, type CaseDetail, type Glossary, type LesionKey, type Mode, type Sentence } from '../api'
import { DME_LABEL, ROUTING, eyeName, STAGE_CLINICAL, isValidation, num, routingAlertTone, validationSource, pct, when } from '../format'
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
    api.cases().then((d) => { if (active) setNextId(d.cases.find((x) => x.status === 'new' && x.id !== id)?.id ?? null) }, () => { if (active) setNextId(null) })
    return () => { active = false }
  }, [id, c?.status])
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
              {c.status === 'reviewed' ? <Badge tone="success">Reviewed</Badge> : <Badge tone="neutral">Awaiting review</Badge>}
            </span>
          </h1>
          <div className="mt-3"><Badge tone={ROUTING[c.routing.state].tone} dot>{c.routing.label}</Badge></div>
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
                <p className="text-secondary font-medium text-text-secondary">AI-suggested stage</p>
                {c.assist.confidence_level ? <ConfidenceBadge level={c.assist.confidence_level} /> : <Badge>Confidence not calibrated</Badge>}
              </div>
              <div className={cn('mt-3 inline-flex flex-col rounded-card border px-4 py-3', STAGE_BOX[a.grading!.grade])}>
                <span className="font-display text-display-sm leading-none">Stage {a.grading!.grade}</span>
                <span className="mt-1 text-secondary font-medium">{STAGE_CLINICAL[a.grading!.grade]}</span>
              </div>
              {mode === 'simple' && <p className="mt-2 text-body text-text-secondary">{stagePlain(a.grading!.grade)}</p>}
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

          {(ok || a.status === 'rejected') && (
            <Card title="Clinician review" subtitle={a.status === 'rejected' ? 'Record the image as ungradable and arrange a retake.' : 'Record your assessment independently of the AI suggestion.'}>
              <ReviewForm key={c.id} c={c} onSaved={(d) => { setCase(d); setToast('Review saved. It is stored with the case for model feedback.') }} />
              <p className="mt-4 rounded-control bg-surface-subtle p-3 text-caption text-text-secondary">Saved corrections are recorded here. They do not currently update the generated report or its routing.</p>
              <Button variant="secondary" icon={FileText} className="mt-4 w-full"
                onClick={() => navigate(`/patients/${encodeURIComponent(c.patient_ref)}/report?case=${c.id}`)}>View detailed report</Button>
            </Card>
          )}

          <RoutingCard c={c} />

          {ok && (
            <Card title="Predicted lesion regions" subtitle="Connected regions, not clinically verified lesion counts.">
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

export function ReviewForm({ c, onSaved }: { c: Pick<CaseDetail, 'analysis' | 'id' | 'reviews'>; onSaved: (c: CaseDetail) => void }) {
  const [dirty, setDirty] = useState(false)
  useUnsavedChanges(dirty, 'This clinician review has unsaved changes. Leave this case?')
  const [reviewer, setReviewer] = useState('')
  const rejected = c.analysis.status === 'rejected'
  const [decision, setDecision] = useState<'agree' | 'disagree' | 'ungradable'>(rejected ? 'ungradable' : 'agree')
  const [stage, setStage] = useState('')
  const [dme, setDme] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [touched, setTouched] = useState(false)
  const reviewerError = touched && !reviewer.trim() ? 'Enter your name or initials.' : undefined
  const stageError = touched && decision === 'disagree' && stage === '' ? 'Choose the stage you would give.' : undefined

  async function save() {
    if (busy) return
    setTouched(true)
    if (!reviewer.trim() || (decision === 'disagree' && stage === '')) { document.getElementById(!reviewer.trim() ? 'reviewer' : 'stage')?.focus(); return }
    setBusy(true)
    setError(null)
    try {
      const saved = await api.review(c.id, { reviewer: reviewer.trim(), decision, corrected_stage: decision === 'disagree' ? Number(stage) : null, corrected_dme: decision === 'ungradable' ? null : dme || null, note })
      setDirty(false)
      onSaved(saved)
      setNote('')
      setTouched(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Alert tone="danger" title="Review not saved">{error}</Alert>}
      <fieldset disabled={busy} className="contents" onChange={() => setDirty(true)}>
      {!rejected && <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1 2xl:grid-cols-2">
        <Button variant={decision === 'agree' ? 'primary' : 'secondary'} icon={CircleCheck} aria-pressed={decision === 'agree'} onClick={() => { setDecision('agree'); setDirty(true) }}>Confirm stage</Button>
        <Button variant={decision === 'disagree' ? 'primary' : 'secondary'} icon={PencilLine} aria-pressed={decision === 'disagree'} onClick={() => { setDecision('disagree'); setDirty(true) }}>Change stage</Button>
      </div>}
      {!rejected && <button type="button" onClick={() => { setDecision('ungradable'); setDirty(true) }} aria-pressed={decision === 'ungradable'}
        className={cn('self-start text-secondary underline underline-offset-2', decision === 'ungradable' ? 'font-semibold text-brand-800' : 'text-text-secondary hover:text-text-primary')}>
        Mark the image ungradable instead
      </button>}
      <Field id="reviewer" label="Reviewer" error={reviewerError}>
        <Input id="reviewer" autoComplete="name" maxLength={60} disabled={busy} value={reviewer} invalid={!!reviewerError} onChange={(e) => setReviewer(e.target.value)} placeholder="Name or initials" />
      </Field>
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
      <Field id="note" label="Note (optional)">
        <textarea id="note" value={note} maxLength={1000} rows={3} onChange={(e) => setNote(e.target.value)}
          className="w-full rounded-control border border-border-strong bg-surface-card px-3 py-2 text-body text-text-primary hover:border-neutral-400" />
      </Field>
      <div className="flex justify-end">
        <Button onClick={save} state={busy ? 'loading' : 'default'}>
          Save review: {decision === 'agree' ? 'confirm' : decision === 'disagree' ? 'change stage' : 'ungradable'}
        </Button>
      </div>
      </fieldset>
      {c.reviews.length > 0 && (
        <div className="border-t border-border-default pt-4">
          <h3 className="text-secondary font-semibold text-text-secondary">Previous reviews</h3>
          <ul className="mt-2 flex flex-col gap-2">
            {c.reviews.map((r) => (
              <li key={r.id} className="text-secondary">
                <span className="font-medium">{r.reviewer}</span> · {when(r.created)} · {r.decision === 'disagree' ? `Changed: stage ${r.corrected_stage}` : r.decision === 'agree' ? 'Confirmed' : 'Ungradable'}
                {r.note && <span className="text-text-secondary"> · {r.note}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function RoutingCard({ c }: { c: CaseDetail }) {
  const r = c.routing
  return (
    <Card title="AI-suggested routing">
      <div className="mb-3"><Badge tone={ROUTING[r.state].tone} dot>{r.label}</Badge></div>
      <Alert tone={routingAlertTone(r.state)} title={r.state === 'ROUTINE_RESCREEN_ELIGIBLE' ? 'Why it is eligible' : 'Why it needs attention'}>
        <ul className="flex list-disc flex-col gap-1 pl-4">{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
        {r.previous && (
          <p className="mt-2">Previous visit ({r.previous.case_id}, {r.previous.created.slice(0, 10)}): signed by {r.previous.reviewer},{' '}
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
    <Card title={`Patient ${c.patient_ref}`} subtitle="AI summary across recorded eyes; clinician review required"
      actions={<a {...linkProps(`/patients/${encodeURIComponent(c.patient_ref)}/report?case=${c.id}`)} className="text-secondary font-medium text-text-link">Open report</a>}>
      <div className="flex flex-col gap-3">
        {p.eyes.map((e) => (
          <Row key={e.case_id} current={e.case_id === c.id}>
            <span>{eyeName(e.eye)} {e.case_id !== c.id && <a {...linkProps(`/cases/${e.case_id}`)} className="text-text-link">({e.case_id})</a>}</span>
            <span className="flex flex-wrap items-center gap-2 text-right">
              {e.stage == null ? 'Not assessable' : `Stage ${e.stage} · ${stageName(e.stage)}`}
              <Badge tone={ROUTING[e.state].tone}>{ROUTING[e.state].label}</Badge>
            </span>
          </Row>
        ))}
        <Alert tone={routingAlertTone(p.state)} title={`Patient: ${p.label}`}>
          {p.notes.length > 0 && <ul className="flex list-disc flex-col gap-1 pl-4">{p.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          <p className="mt-1">{p.note}</p>
          <p className="mt-1 text-caption">Operating point: {p.operating_point.wording}.{!p.operating_point.valid && ' Routine routing is switched off for the model currently in use.'}</p>
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
