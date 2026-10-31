import { ArrowLeft, Download, Printer } from 'lucide-react'
import { useRef, useState } from 'react'
import { Alert, Button, Segmented, Tabs } from '../../design/components'
import { api } from '../api'
import { navigate } from '../router'

// The report itself is one server-rendered document (backend/templates/report.html): the same HTML is previewed here
// and printed to PDF, so the screen and the PDF cannot drift apart.
export function Report({ patient, caseId }: { patient: string; caseId: string | null }) {
  const [kind, setKind] = useState<'doctor' | 'patient'>('doctor')
  const [lang, setLang] = useState<'en' | 'hi'>('en')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const frame = useRef<HTMLIFrameElement>(null)
  const effectiveLang = kind === 'doctor' ? 'en' : lang
  const src = api.reportUrl(patient, kind, effectiveLang, 'html')

  async function download() {
    setBusy(true)
    setNote(null)
    try {
      const r = await fetch(api.reportUrl(patient, kind, effectiveLang, 'pdf'))
      if (!r.ok) throw new Error((await r.json()).detail ?? `PDF failed (${r.status})`)
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = `${patient}_${kind}${kind === 'patient' ? `_${lang}` : ''}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      // Server-side PDF needs Microsoft Edge; the browser's own print dialog produces the same document.
      setNote(`${(e as Error).message}. Opening the print dialog instead; choose “Save as PDF”.`)
      frame.current?.contentWindow?.print()
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">Patient report</p>
          <h1 className="font-display text-display-sm">Report · {patient}</h1>
          <p className="mt-1 text-secondary text-text-secondary">Patient-level: the latest photograph of each eye. The worst eye decides the suggested follow-up.</p>
        </div>
        <div className="flex items-center gap-2">
          {caseId && <Button variant="ghost" icon={ArrowLeft} onClick={() => navigate(`/cases/${caseId}`)}>Back to case</Button>}
          <Button variant="secondary" icon={Printer} onClick={() => frame.current?.contentWindow?.print()}>Print</Button>
          <Button icon={Download} onClick={download} state={busy ? 'loading' : 'default'}>Download PDF</Button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <Tabs value={kind} onChange={(v) => setKind(v as 'doctor' | 'patient')} tabs={[{ value: 'doctor', label: 'Doctor report' }, { value: 'patient', label: 'Patient summary' }]} />
        <div className="flex items-center gap-3">
          <span className="text-secondary text-text-secondary">Language</span>
          <Segmented label="Report language" value={effectiveLang} onChange={setLang} state={kind === 'doctor' ? 'disabled' : 'default'}
            options={[{ value: 'en', label: 'English' }, { value: 'hi', label: 'हिंदी' }]} />
        </div>
      </div>
      {kind === 'doctor' && <p className="mb-4 text-caption text-text-muted">The doctor report is in English; the patient summary is available in English and Hindi.</p>}
      {kind === 'patient' && lang === 'hi' && (
        <div className="mb-4"><Alert tone="info" title="Hindi wording awaits clinical review">The Hindi text is fixed wording written for this prototype; a native-speaking clinician has not yet reviewed it.</Alert></div>
      )}
      {note && <div className="mb-4"><Alert tone="warning" title="PDF created by the browser">{note}</Alert></div>}

      <div className="rounded-card border border-border-default bg-surface-subtle">
        <iframe ref={frame} key={src} src={src} title={`${kind === 'doctor' ? 'Doctor report' : 'Patient summary'} preview`} className="block h-[1100px] w-full rounded-card" />
      </div>
    </>
  )
}
