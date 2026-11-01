import { ArrowLeft, Download, ExternalLink, Printer, RefreshCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Segmented, Skeleton, Tabs } from '../../design/components'
import { api } from '../api'
import { navigate } from '../router'
import { PageHeader } from '../Shell'

// The unchanged server document remains the source for both the preview and PDF.
export function Report({ patient, caseId }: { patient: string; caseId: string | null }) {
  const [kind, setKind] = useState<'doctor' | 'patient'>('doctor')
  const [lang, setLang] = useState<'en' | 'hi'>('en')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ src: string; html?: string; error?: string } | null>(null)
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const frame = useRef<HTMLIFrameElement>(null)
  const effectiveLang = kind === 'doctor' ? 'en' : lang
  const src = api.reportUrl(patient, kind, effectiveLang, 'html')
  const current = preview?.src === src ? preview : null
  const ready = !!current?.html && loadedSrc === src
  useEffect(() => {
    const controller = new AbortController()
    setPreview(null); setLoadedSrc(null)
    fetch(src, { signal: controller.signal }).then(async r => { if (!r.ok) throw new Error(`Report unavailable (${r.status}). Check that this patient has saved cases.`); return r.text() })
      .then(html => setPreview({ src, html }), error => { if (error.name !== 'AbortError') setPreview({ src, error: error.message }) })
    return () => controller.abort()
  }, [src, retry])
  function print() {
    try { frame.current?.contentWindow?.print() } catch { setNote('The preview could not open the print dialog. Open the full report and print from that window.') }
  }
  async function download() {
    setBusy(true); setNote(null)
    try {
      const r = await fetch(api.reportUrl(patient, kind, effectiveLang, 'pdf'))
      if (!r.ok) { const detail = await r.json().catch(() => null); throw new Error(detail?.detail ?? `PDF export failed (${r.status})`) }
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url; a.download = `${patient}_${kind}${kind === 'patient' ? `_${lang}` : ''}.pdf`; a.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (error) {
      setNote(`${(error as Error).message}. ${ready ? 'Opening the print dialog; choose Save as PDF.' : 'Once the preview loads, use Print or open the full report.'}`)
      if (ready) print()
    } finally { setBusy(false) }
  }
  return <>
    <PageHeader title={`Report · ${patient}`} subtitle="Latest recorded photograph of each eye. Generated from the AI analysis and existing routing rules."
      actions={<>{caseId && <Button variant="ghost" icon={ArrowLeft} onClick={() => navigate(`/cases/${caseId}`)}>Back to case</Button>}<Button variant="secondary" icon={Printer} disabled={!ready} onClick={print}>Print</Button><Button icon={Download} disabled={!ready} onClick={download} state={busy ? 'loading' : 'default'}>Download PDF</Button></>} />
    <div className="mb-6 rounded-control border border-status-warning-border bg-status-warning-tint px-4 py-3 text-secondary text-status-warning-text">
      <strong className="font-semibold">Report provenance:</strong> saved clinician corrections do not currently update this report or its routing. Review the case record before using or sharing the report.
    </div>
    <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
      <Tabs value={kind} onChange={v => { setKind(v as 'doctor' | 'patient'); setNote(null) }} tabs={[{ value: 'doctor', label: 'Doctor report' }, { value: 'patient', label: 'Patient summary' }]} />
      <Segmented label="Report language" value={effectiveLang} onChange={setLang} state={kind === 'doctor' ? 'disabled' : 'default'} options={[{ value: 'en', label: 'English' }, { value: 'hi', label: 'हिंदी' }]} />
    </div>
    {kind === 'doctor' && <p className="mb-4 text-caption text-text-muted">Doctor reports are in English. Patient summaries are available in English and Hindi.</p>}
    {kind === 'patient' && lang === 'hi' && <div className="mb-4"><Alert title="Hindi wording awaits clinical review">The fixed Hindi wording has not yet been reviewed by a native-speaking clinician.</Alert></div>}
    {note && <div className="mb-4"><Alert tone="warning" title="PDF export unavailable">{note}</Alert></div>}
    {current?.error ? <Alert tone="danger" title="Could not load this report" action={<Button variant="secondary" icon={RefreshCcw} onClick={() => setRetry(n => n + 1)}>Try again</Button>}>{current.error}</Alert> : <div className="overflow-hidden rounded-card border border-border-default bg-surface-subtle">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default bg-surface-card px-4 py-3"><p className="text-caption text-text-secondary" role="status">{ready ? 'Report preview · server-generated document' : 'Preparing report preview…'}</p><a href={src} target="_blank" rel="noreferrer" className="inline-flex min-h-[32px] items-center gap-2 text-caption font-medium">Open full report<ExternalLink size={14} aria-hidden /></a></div>
      {!current?.html && <div className="p-6"><Skeleton className="h-[480px] w-full" /></div>}
      {current?.html && <iframe ref={frame} key={src} srcDoc={current.html} onLoad={() => setLoadedSrc(src)} title={`${kind === 'doctor' ? 'Doctor report' : 'Patient summary'} preview`} className="block h-[78vh] min-h-[480px] w-full bg-white" />}
    </div>}
  </>
}
