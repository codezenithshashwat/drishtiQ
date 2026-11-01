import { Aperture, CircleCheck, Crosshair, Eye as EyeIcon, FileText, ImageUp, ListChecks, ScanEye, Sun, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent } from 'react'
import { Alert, Badge, Button, Card, Checkbox, Field, IconCircle, Input, Progress, Segmented, StageBadge, cn } from '../../design/components'
import { api, type CaseDetail, type Eye } from '../api'
import { ROUTING, STAGE_CLINICAL, VISIT, eyeName } from '../format'
import { linkProps, navigate } from '../router'
import { PageHeader } from '../Shell'
import { useUnsavedChanges } from '../useUnsavedChanges'

const MAX_MB = 25
type Slot = { file: File; preview: string }
type Done = { eye: Eye; case?: CaseDetail; error?: string }

const STEPS = ['Prepare screening', 'Analyse photographs', 'Review results']

export function NewScreening() {
  const [patient, setPatient] = useState('')
  const [uploadMode, setUploadMode] = useState<'individual' | 'batch'>('individual')
  const [fileMessage, setFileMessage] = useState<string | null>(null)
  const previewUrls = useRef(new Set<string>())
  const inFlight = useRef(false)
  const newKey = () => (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`)
  const visitKey = useRef(newKey())
  useEffect(() => { const urls = previewUrls.current; return () => { urls.forEach(url => URL.revokeObjectURL(url)) } }, [])
  // ADR-040: at most two optional intake questions; either one sends the case to clinician review.
  const [intake, setIntake] = useState({ vision_problems: false, prior_treatment: false })
  const [eyeUnknown, setEyeUnknown] = useState(false)
  const [slots, setSlots] = useState<Partial<Record<Eye, Slot>>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [done, setDone] = useState<Done[] | null>(null)
  const [touched, setTouched] = useState(false)
  const [batch, setBatch] = useState<File[] | null>(null)

  const eyes: Eye[] = eyeUnknown ? ['unknown'] : ['right', 'left']
  const chosen = eyes.filter((e) => slots[e])
  useUnsavedChanges(uploadMode === 'individual' && !batch && !done && (!!patient || chosen.length > 0 || !!busy || intake.vision_problems || intake.prior_treatment || eyeUnknown), busy ? 'Analysis is in progress. Leaving may hide its results; check the worklist before retrying. Leave this screen?' : 'This screening has unsaved details. Leave this screen?')
  const patientError = touched && !patient.trim() ? 'Enter a patient ID.' : undefined
  const fileError = touched && chosen.length === 0 ? 'Add a fundus photograph of at least one eye.' : undefined
  const tooBig = chosen.filter((e) => slots[e]!.file.size > MAX_MB * 2 ** 20)
  const step = done ? 3 : busy ? 2 : 1

  function choose(eye: Eye, files: FileList | null | undefined) {
    const list = files ? Array.from(files) : []
    if (list.length > 1) { setFileMessage('Choose one photograph for this eye. Use Batch screening to upload multiple photographs.'); return }
    const f = list[0]
    if (!f) return
    setFileMessage(null)
    const preview = URL.createObjectURL(f)
    previewUrls.current.add(preview)
    if (slots[eye]) { URL.revokeObjectURL(slots[eye]!.preview); previewUrls.current.delete(slots[eye]!.preview) }
    setSlots(s => ({ ...s, [eye]: { file: f, preview } }))
  }

  function clear(eye: Eye) {
    if (slots[eye]) { URL.revokeObjectURL(slots[eye]!.preview); previewUrls.current.delete(slots[eye]!.preview) }
    setSlots((s) => { const n = { ...s }; delete n[eye]; return n })
  }

  async function submit() {
    if (inFlight.current) return
    setTouched(true)
    if (!patient.trim() || chosen.length === 0 || tooBig.length) { document.getElementById(!patient.trim() ? 'patient' : 'photographs')?.focus(); return }
    inFlight.current = true
    const out: Done[] = []
    // One screening visit (encounter) pairs the right and left photographs. The key makes a retried submit reuse it.
    let encounterId: string | undefined
    if (!eyeUnknown) {
      try {
        setBusy('Starting the screening visit…')
        encounterId = (await api.createEncounter(patient.trim(), visitKey.current)).id
      } catch (e) {
        setBusy(null); inFlight.current = false
        setDone(chosen.map((eye) => ({ eye, error: `The visit could not be started: ${(e as Error).message}` })))
        return
      }
    }
    for (const eye of chosen) {
      setBusy(`Analysing the ${eyeName(eye).toLowerCase()}…`)
      try {
        out.push({ eye, case: await api.createCase(slots[eye]!.file, patient.trim(), eye, intake, encounterId) })
      } catch (e) {
        out.push({ eye, error: (e as Error).message })
      }
    }
    setBusy(null)
    inFlight.current = false
    setDone(out)
  }

  function restart() {
    Object.values(slots).forEach((s) => s && URL.revokeObjectURL(s.preview))
    previewUrls.current.clear()
    setFileMessage(null)
    setSlots({}); setDone(null); setPatient(''); setTouched(false); setIntake({ vision_problems: false, prior_treatment: false })
    visitKey.current = newKey()  // the next screening is a new visit
  }

  if (uploadMode === 'batch' && !batch) return <BatchPicker onFiles={setBatch} onBack={() => setUploadMode('individual')} />
  if (batch) return <BatchUpload files={batch} onCancel={() => setBatch(null)} />

  return (
    <>
      <PageHeader title="New screening" subtitle="Start with a patient reference and a photograph of each eye." actions={<Segmented label="Upload mode" value={uploadMode} state={busy ? 'disabled' : 'default'} onChange={setUploadMode} options={[{value: 'individual', label: 'Individual'}, {value: 'batch', label: 'Batch screening'}]} />} />
      <ol aria-label="Progress" className="mb-6 grid grid-cols-1 gap-2 sm:grid-cols-3">
        {STEPS.map((label, i) => {
          const n = i + 1, current = n === step, past = n < step
          return (
            <li key={label} aria-current={current ? 'step' : undefined}
              className={cn('flex items-center gap-3 rounded-control border px-3 py-2', current ? 'border-brand-100 bg-surface-card shadow-card' : 'border-transparent')}>
              <span className={cn('grid h-8 w-8 shrink-0 place-items-center rounded-full text-secondary font-semibold',
                current ? 'bg-cta text-text-onBrand' : past ? 'bg-brand-50 text-brand-800' : 'bg-surface-subtle text-text-secondary')}>
                {past ? <CircleCheck size={16} strokeWidth={2} aria-hidden /> : n}
              </span>
              <span className={cn('text-secondary', current ? 'font-semibold text-brand-800' : 'text-text-secondary')}>{label}</span>
            </li>
          )
        })}
      </ol>

      {done ? <Results patient={patient.trim()} done={done} onRestart={restart} /> : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Card title="Patient details" subtitle="Use the clinic's ID, not a name.">
            <fieldset disabled={!!busy} className="m-0 flex min-w-0 flex-col gap-5 border-0 p-0">
              <Field id="patient" label="Patient ID / reference" error={patientError}>
                <Input id="patient" name="patient-reference" autoComplete="off" spellCheck={false} value={patient} maxLength={40} invalid={!!patientError} onChange={(e) => setPatient(e.target.value)} placeholder="e.g. CLN-20417" />
              </Field>
              <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
                <legend className="mb-1 text-secondary font-medium">Optional intake</legend>
                <Checkbox checked={intake.vision_problems} label="Patient reports vision problems" onChange={(v) => setIntake((i) => ({ ...i, vision_problems: v }))} />
                <Checkbox checked={intake.prior_treatment} label="Previous eye treatment / laser" onChange={(v) => setIntake((i) => ({ ...i, prior_treatment: v }))} />
              </fieldset>
              <Checkbox checked={eyeUnknown} label="The eye (right / left) was not recorded" onChange={(v) => setEyeUnknown(v)} />
              <div className="rounded-control bg-surface-subtle p-3 text-caption text-text-secondary">
                Both eyes are needed for a complete screening. With one eye only, the patient's result says the screening is incomplete.
              </div>
            </fieldset>
          </Card>

          <div className="flex flex-col gap-6">
            <Card title="Upload fundus photographs" subtitle="One image per eye. JPEG, PNG, TIFF or BMP; up to 25 MB each.">
              <fieldset id="photographs" tabIndex={-1} disabled={!!busy} aria-label="Fundus photographs" className={cn('m-0 grid min-w-0 grid-cols-1 gap-4 border-0 p-0', eyes.length === 2 && 'md:grid-cols-2')}>
                {eyes.map(eye => <EyeSlot key={eye} eye={eye} slot={slots[eye]} disabled={!!busy} error={!!fileError} onChoose={f => choose(eye, f)} onClear={() => clear(eye)} />)}
              </fieldset>
              {busy && <div className="mt-4 rounded-control bg-brand-50 p-4" role="status"><p className="font-medium text-brand-800">{busy}</p><p className="mt-1 text-secondary text-text-secondary">Checking quality and preparing AI grading and image overlays. Keep this screen open.</p></div>}
              {fileMessage && <p role="alert" className="mt-3 text-secondary text-status-danger-text">{fileMessage}</p>}
              {fileError && <p role="alert" className="mt-2 text-caption text-status-danger-text">{fileError}</p>}
              {tooBig.length > 0 && <p className="mt-2 text-caption text-status-danger-text">The photograph of the {tooBig.map((e) => eyeName(e).toLowerCase()).join(' and ')} is larger than {MAX_MB} MB.</p>}
              {!eyeUnknown && chosen.length === 1 && <p className="mt-3 text-caption text-status-warning-text">Only the {eyeName(chosen[0]).toLowerCase()} is added. This visit will show as incomplete until the other eye is photographed.</p>}
              <div className="mt-5 flex flex-wrap justify-end gap-2">
                <Button variant="secondary" onClick={() => navigate('/worklist')} state={busy ? 'disabled' : 'default'}>Cancel</Button>
                <Button icon={ScanEye} onClick={submit} state={busy ? 'loading' : 'default'}>
                  {busy ? 'Analysing…' : chosen.length === 2 ? 'Analyse both eyes' : 'Analyse'}
                </Button>
              </div>
            </Card>

            <Card title="Image guidelines">
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {([[Sun, 'Well lit and in focus', 'Very dark or blurred photographs are flagged for a retake.'],
                  [Aperture, 'Whole retina visible', 'The round field of view should fill most of the frame.'],
                  [Crosshair, 'Macula-centred, 45°', 'The standard screening view; the centre of vision near the middle.'],
                  [EyeIcon, 'One eye per photograph', 'Label it right or left so both eyes can be combined.']] as const).map(([icon, title, body]) => (
                  <li key={title} className="flex gap-3">
                    <IconCircle icon={icon} size="sm" />
                    <span><span className="block text-body font-medium">{title}</span><span className="block text-caption text-text-secondary">{body}</span></span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  )
}

function EyeSlot({ eye, slot, error, disabled, onChoose, onClear }: { eye: Eye; slot?: Slot; error: boolean; disabled?: boolean; onChoose: (f: FileList | null) => void; onClear: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const onDrop = (e: DragEvent) => { e.preventDefault(); if (!disabled) onChoose(e.dataTransfer.files) }
  const title = eye === 'unknown' ? 'Photograph (eye not recorded)' : eyeName(eye)
  return (
    <div onDragOver={(e) => e.preventDefault()} onDrop={onDrop}
      className={cn('flex min-h-[260px] flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed p-4 text-center',
        error && !slot ? 'border-status-danger-border bg-status-danger-tint' : slot ? 'border-border-default bg-surface-card' : 'border-border-strong bg-surface-subtle')}>
      <p className="text-section font-semibold">{title}</p>
      {slot ? (
        <>
          <img src={slot.preview} alt={`Selected photograph, ${title.toLowerCase()}`} className="max-h-[180px] rounded-control bg-surface-viewer" />
          <p className="max-w-full break-all text-caption text-text-secondary">{slot.file.name} · {(slot.file.size / 2 ** 20).toFixed(1)} MB</p>
          <div className="flex gap-2">
            <Button variant="secondary" compact onClick={() => input.current?.click()}>Replace</Button>
            <Button variant="ghost" compact icon={Trash2} onClick={onClear} aria-label={`Remove the ${title.toLowerCase()} photograph`}>Remove</Button>
          </div>
        </>
      ) : (
        <>
          <IconCircle icon={ImageUp} size="lg" />
          <p className="text-body font-medium">Drop a photograph here</p>
          <p className="text-caption text-text-muted">JPEG, PNG, TIFF or BMP · up to {MAX_MB} MB · at least 256 px per side</p>
          <Button variant="secondary" compact onClick={() => input.current?.click()}>Choose file</Button>
        </>
      )}
      <input ref={input} type="file" disabled={disabled} accept="image/jpeg,image/png,image/tiff,image/bmp" className="sr-only" aria-label={`Fundus photograph, ${title.toLowerCase()}`}
        onChange={(e) => { onChoose(e.target.files); e.target.value = '' }} />
    </div>
  )
}

/** Step 4: what the AI did with each photograph, with retake reasons in plain words straight away. */
function Results({ patient, done, onRestart }: { patient: string; done: Done[]; onRestart: () => void }) {
  // The patient summary of the last analysed eye already includes the eyes analysed before it.
  const latest = [...done].reverse().find((d) => d.case)?.case
  return (
    <div className="flex flex-col gap-6">
      <div className={cn('grid grid-cols-1 gap-6', done.length === 2 && 'lg:grid-cols-2')}>
        {done.map((d) => {
          const c = d.case, a = c?.analysis
          const retake = a && (a.status === 'rejected' || !a.quality.usable)
          return (
            <Card key={d.eye} title={eyeName(d.eye)} actions={c && <Badge tone={ROUTING[c.routing.state].tone} dot>AI: {ROUTING[c.routing.state].label}</Badge>}>
              {d.error && <Alert tone="danger" title="This photograph could not be analysed">{d.error}</Alert>}
              {c && a && (
                <div className="flex flex-col gap-4">
                  {retake ? (
                    <Alert tone="warning" title={a.status === 'rejected' ? 'Retake: not a gradable fundus photograph' : 'Retake recommended: low image quality'}>
                      {a.quality.issues.join(' ') || 'No retinal field was detected.'} Take the photograph again before the patient leaves.
                    </Alert>
                  ) : (
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-caption text-text-secondary">AI severity suggestion</span>
                      <StageBadge stage={a.grading!.grade} label={STAGE_CLINICAL[a.grading!.grade]} />
                      {c.assist.available && <span className="text-secondary text-text-secondary">Chance it needs a specialist: {Math.round(100 * (c.assist.p_referable ?? 0))}%</span>}
                    </div>
                  )}
                  <ul className="flex list-disc flex-col gap-1 pl-4 text-secondary text-text-secondary">{c.routing.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  <div className="flex flex-wrap gap-2">
                    <Button icon={ScanEye} onClick={() => navigate(`/cases/${c.id}`)}>Open case {c.id}</Button>
                  </div>
                </div>
              )}
            </Card>
          )
        })}
      </div>
      {latest && (
        <Alert tone={latest.patient.effective.missing_eyes.length ? 'warning' : 'info'} title={`Visit for ${patient}: ${VISIT[latest.patient.effective.state].label}`}>
          {latest.patient.effective.missing_eyes.length > 0 && `No ${latest.patient.effective.missing_eyes.join(' or ')}-eye photograph yet. `}
          {latest.patient.ai_label}. {latest.patient.notes.join(' ')} The next action is set only when a clinician signs each eye in Specialist Attention.
        </Alert>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" onClick={onRestart}>Screen another patient</Button>
        <Button variant="secondary" icon={ListChecks} onClick={() => navigate('/worklist')}>Go to Specialist Attention</Button>
        {latest && (
          <a {...linkProps(`/patients/${encodeURIComponent(patient)}/report?case=${encodeURIComponent(latest.id)}`)}
            className="inline-flex h-control items-center gap-2 rounded-control bg-cta px-4 text-body font-medium text-text-onBrand no-underline shadow-card hover:bg-cta-hover">
            <FileText size={16} strokeWidth={1.75} aria-hidden />Patient report
          </a>
        )}
      </div>
    </div>
  )
}


type Item = { file: File; patient: string; state: 'waiting' | 'analysing' | 'done' | 'failed'; caseId?: string; message?: string }

/** Patient ID from the file name: the part before the extension, limited to the 40 characters the backend accepts. */
const idFromName = (name: string) => name.replace(/\.[^.]+$/, '').replace(/\s+/g, '-').slice(0, 40) || 'unnamed'

function BatchUpload({ files, onCancel }: { files: File[]; onCancel: () => void }) {
  const [eye, setEye] = useState<Eye>('unknown')  // camp photographs rarely record the eye
  const [items, setItems] = useState<Item[]>(() => files.map((f) => ({ file: f, patient: idFromName(f.name), state: 'waiting' })))
  const [running, setRunning] = useState(false)
  const done = items.filter((i) => i.state === 'done' || i.state === 'failed').length
  const finished = done === items.length && items.length > 0
  const failed = items.filter((i) => i.state === 'failed').length
  useUnsavedChanges(!finished, running ? 'Batch analysis is still running. Leave this screen? Check the worklist before retrying any photographs.' : 'This batch contains photographs that have not finished processing. Leave this screen?')

  async function runAll() {
    if (running) return
    setRunning(true)
    for (let k = 0; k < items.length; k++) {
      if (items[k].state === 'done') continue
      setItems((xs) => xs.map((x, i) => (i === k ? { ...x, state: 'analysing', message: undefined } : x)))
      const it = items[k]
      try {
        if (!it.patient.trim()) throw new Error('Enter a patient reference before analysing this photograph.')
        if (it.file.size > MAX_MB * 2 ** 20) throw new Error(`The file is larger than ${MAX_MB} MB.`)
        const c = await api.createCase(it.file, it.patient.trim(), eye)
        setItems((xs) => xs.map((x, i) => (i === k ? { ...x, state: 'done', caseId: c.id } : x)))
      } catch (e) {
        setItems((xs) => xs.map((x, i) => (i === k ? { ...x, state: 'failed', message: (e as Error).message } : x)))
      }
    }
    setRunning(false)
  }

  const badge = (i: Item) => i.state === 'done' ? <Badge tone="success">Added</Badge> : i.state === 'failed' ? <Badge tone="danger">Failed</Badge>
    : i.state === 'analysing' ? <Badge tone="brand">Analysing</Badge> : <Badge>Waiting</Badge>

  return (
    <>
      <PageHeader title="Screening camp upload" subtitle={`${items.length} photographs. Each becomes a single-eye case; the patient ID is taken from the file name and can be edited before you start.`} />
      <Card title="Photographs" actions={
        <Segmented label="Eye for all photographs" value={eye} onChange={setEye} state={running ? 'disabled' : 'default'}
          options={[{ value: 'unknown', label: 'Not recorded' }, { value: 'right', label: 'All right' }, { value: 'left', label: 'All left' }]} />
      } footer={
        <>
          <Button variant="secondary" onClick={onCancel} state={running ? 'disabled' : 'default'}>{finished ? 'Upload more' : 'Cancel'}</Button>
          {finished && <Button variant={failed ? 'secondary' : 'primary'} icon={ListChecks} onClick={() => navigate('/worklist')}>Go to the worklist</Button>}
          {(!finished || failed > 0) && (
            <Button icon={ScanEye} onClick={runAll} state={running ? 'loading' : 'default'}>
              {running ? 'Analysing…' : failed ? `Retry ${failed} failed` : `Analyse ${items.length} photographs`}
            </Button>
          )}
        </>
      }>
        <div className="mb-4"><Progress value={items.length ? (100 * done) / items.length : 0} label={`${done} of ${items.length} processed`} /></div>
        <div className="overflow-x-auto" role="region" aria-label="Batch photographs" tabIndex={0}><table className="w-full text-body">
          <caption className="sr-only">Photographs in this upload</caption>
          <thead>
            <tr className="border-b border-border-default text-caption text-text-secondary">
              <th scope="col" className="pb-2 text-left font-medium">File</th>
              <th scope="col" className="pb-2 text-left font-medium">Patient ID</th>
              <th scope="col" className="pb-2 text-left font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it, k) => (
              <tr key={k} className="border-b border-border-default last:border-0 align-top">
                <td className="py-2 pr-4 text-text-secondary">{it.file.name}</td>
                <td className="py-2 pr-4">
                  <Input aria-label={`Patient ID for ${it.file.name}`} value={it.patient} maxLength={40} state={running || it.state === 'done' ? 'disabled' : 'default'}
                    onChange={(e) => setItems((xs) => xs.map((x, i) => (i === k ? { ...x, patient: e.target.value } : x)))} />
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">{badge(it)}{it.caseId && <a {...linkProps(`/cases/${it.caseId}`)} className="text-secondary text-text-link">{it.caseId}</a>}</div>
                  {it.message && <p className="mt-1 text-caption text-status-danger-text">{it.message}</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {finished && items.some((i) => i.state === 'failed') && (
          <p className="mt-3 text-caption text-text-secondary">Check the worklist before retrying a network failure: a case may already have been saved. Retry skips photographs confirmed as added.</p>
        )}
      </Card>
    </>
  )
}

function BatchPicker({ onFiles, onBack }: { onFiles: (files: File[]) => void; onBack: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  return <>
    <PageHeader title="Batch screening" subtitle="Prepare a group of photographs before starting analysis." actions={<Button variant="secondary" onClick={onBack}>Individual screening</Button>} />
    <Card title="Choose fundus photographs" subtitle="Each file creates a single-eye case. You can check patient references and eye labels before analysis.">
      <div className="flex min-h-[300px] flex-col items-center justify-center gap-4 rounded-control border-2 border-dashed border-border-strong bg-surface-subtle p-6 text-center"
        onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files)) }}>
        <ImageUp size={40} strokeWidth={1.25} aria-hidden className="text-brand-700" />
        <p className="text-section font-medium">Drop your photographs here</p>
        <p className="max-w-measure text-secondary text-text-secondary">JPEG, PNG, TIFF or BMP. Up to 25 MB per image. Patient references initially come from file names.</p>
        <Button icon={ImageUp} onClick={() => input.current?.click()}>Choose photographs</Button>
        <input ref={input} aria-label="Batch fundus photographs" type="file" multiple accept="image/jpeg,image/png,image/tiff,image/bmp" className="sr-only" onChange={e => { if (e.target.files?.length) onFiles(Array.from(e.target.files)) }} />
      </div>
    </Card>
  </>
}
