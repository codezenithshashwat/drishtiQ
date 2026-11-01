import { Inbox, RefreshCcw, Search, Upload } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, Checkbox, ConfidenceBadge, EmptyState, Input, Pagination, Skeleton, StageBadge, Table, Tabs, cn, type Column } from '../../design/components'
import { api, type CaseRow, type ModelCard, type Queue, type Settings } from '../api'
import { DME_LABEL, QUEUES, ROUTING, STAGE_CLINICAL, eyeName, isValidation, nextActionInfo, pct, queueFromTab, when } from '../format'
import { href, linkProps, navigate } from '../router'
import { PageHeader } from '../Shell'

type Data = Awaited<ReturnType<typeof api.cases>>
const PER_PAGE = 50
const QUEUE_TONE: Record<Queue, 'danger' | 'warning' | 'info' | 'slate' | 'success'> = { attention: 'danger', awaiting: 'warning', retake: 'info', routine: 'slate', signed: 'success' }

/** Specialist Attention: who needs my attention, and why. Order comes from the AI's provisional routing; the clinician's
 * signed decision moves a case to Signed and governs its next action. */
export function Worklist({ initialTab, initialQuery }: { initialTab?: string | null; initialQuery?: string | null }) {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Queue | 'all'>(queueFromTab(initialTab))
  const [query, setQuery] = useState(initialQuery ?? '')
  const [page, setPage] = useState(1)
  const [agreement, setAgreement] = useState<ModelCard['agreement'] | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [details, setDetails] = useState(false)
  const [signError, setSignError] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [signing, setSigning] = useState<string | null>(null)

  const load = () => api.cases().then(d => { setData(d); setError(null) }, e => setError(e.message))
  useEffect(() => {
    load()
    api.settings().then(setSettings, () => setSettings(null))
    api.model().then((m) => setAgreement(m.agreement), () => setAgreement(null))
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.cases
      .filter((c) => tab === 'all' || c.queue === tab)
      .filter((c) => !q || c.patient_ref.toLowerCase().includes(q) || c.id.toLowerCase().includes(q))
  }, [data, tab, query])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    params.set('tab', tab)
    if (query) params.set('q', query); else params.delete('q')
    window.history.replaceState({}, '', href('/worklist?' + params.toString()))
  }, [query, tab])

  // 50 rows per page keeps a camp-sized list (hundreds of cases) responsive; order and search span all cases.
  const pages = Math.max(1, Math.ceil(rows.length / PER_PAGE))
  const current = Math.min(page, pages)
  useEffect(() => { setPage(1); setConfirmed(false) }, [tab, query])

  const counts = useMemo(() => {
    const out: Record<string, number> = { all: data?.cases.length ?? 0 }
    for (const c of data?.cases ?? []) out[c.queue] = (out[c.queue] ?? 0) + 1
    return out
  }, [data])
  const routinePile = rows.filter((c) => c.queue === 'routine')

  // Batch sign-off of the routine pile: one signed decision per case, by the signed-in clinician, after explicit confirmation.
  async function signOff() {
    if (signing || !confirmed) return
    setSignError(null)
    let saved = 0
    try {
      for (const c of routinePile) {
        setSigning('Signing ' + (saved + 1) + ' of ' + routinePile.length)
        await api.review(c.id, { decision: 'agree', corrected_stage: null, corrected_dme: null, next_action: 'routine_rescreen', note: 'Batch sign-off of the routine pile' })
        saved++
      }
    } catch (e) {
      setSignError(saved + ' decisions confirmed saved. ' + (e as Error).message + ' Refresh and check the remaining cases before retrying.')
    } finally {
      setSigning(null); setConfirmed(false)
      await load()
    }
  }

  const allColumns: Column<CaseRow>[] = [
    { key: 'why', header: 'Why it is here', width: '260px', render: (c) => (
      <div className="flex min-w-[200px] flex-col gap-1">
        <span><Badge tone={QUEUE_TONE[c.queue]} dot>{c.queue_label}</Badge></span>
        <span className="line-clamp-2 text-caption text-text-secondary" title={c.queue_reason}>{c.queue_reason}</span>
      </div>
    ) },
    { key: 'patient', header: 'Patient', width: '250px', render: (c) => (
      <div className="flex items-center gap-3">
        {c.thumbnail ? <img src={c.thumbnail} alt="" loading="lazy" width={48} height={48} className="h-12 w-12 rounded-control bg-surface-viewer object-cover" /> : <span className="h-12 w-12 rounded-control bg-neutral-200" />}
        <div className="min-w-0">
          <a {...linkProps('/cases/' + encodeURIComponent(c.id))} className="block min-w-[120px] break-words font-semibold text-text-primary no-underline hover:underline">{c.patient_ref}<span className="sr-only">, {eyeName(c.eye)}, case {c.id}</span></a>{isValidation(c.source) && <span className="text-caption text-text-muted">Validation image</span>}
          <div className="flex items-center gap-2 whitespace-nowrap text-caption text-text-muted">
            <span aria-hidden className={cn('grid h-5 w-5 place-items-center rounded-full text-[11px] font-semibold', c.eye === 'unknown' ? 'bg-neutral-100 text-text-secondary' : 'bg-accent-circle text-accent-text')}>
              {c.eye === 'right' ? 'R' : c.eye === 'left' ? 'L' : '?'}
            </span>
            {c.id} · {eyeName(c.eye)}
          </div>
          <Completeness c={c} />
        </div>
      </div>
    ) },
    { key: 'decision', header: 'Clinician decision', width: '190px', render: (c) => (c.effective.signed
      ? <span className="flex flex-col gap-1"><Badge tone={nextActionInfo(c.effective.next_action)?.tone ?? 'neutral'}>{nextActionInfo(c.effective.next_action)?.label}</Badge><span className="text-caption text-text-muted">{c.effective.reviewer} · {c.effective.signed_at ? when(c.effective.signed_at) : ''}</span></span>
      : <span className="text-caption text-text-muted">Not signed{c.effective.legacy_reviews ? ' (historical review only)' : ''}</span>) },
    { key: 'stage', header: 'AI stage (suggestion)', render: (c) => (c.stage == null ? <Badge tone="warning">Not assessable</Badge> : <StageBadge stage={c.stage} label={STAGE_CLINICAL[c.stage]} />) },
    { key: 'routing', header: 'AI routing', width: '160px', render: (c) => <span title={c.routing.reasons.join(' ')}><Badge tone={ROUTING[c.routing.state].tone}>{ROUTING[c.routing.state].label}</Badge></span> },
    { key: 'pref', header: 'P(referable)', numeric: true, width: '120px', render: (c) => <span className="tabular-nums">{c.assist.available ? pct(c.assist.p_referable) : '—'}</span> },
    { key: 'lesions', header: 'Candidate regions', numeric: true, width: '130px', render: (c) => <span className="tabular-nums">{c.stage == null ? '—' : c.lesion_regions}</span> },
    { key: 'conf', header: 'Confidence', width: '170px', render: (c) => (c.assist.confidence_level ? <ConfidenceBadge level={c.assist.confidence_level} /> : <span className="text-text-muted">—</span>) },
    { key: 'dme', header: 'Macula (AI)', width: '100px', render: (c) => (c.dme ? DME_LABEL[c.dme] : '—') },
    { key: 'created', header: 'Added', numeric: true, width: '120px', render: (c) => <span className="whitespace-nowrap text-text-secondary tabular-nums">{when(c.created)}</span> },
  ]
  const columns = allColumns.filter(c => details || !['lesions', 'conf', 'dme', 'routing'].includes(c.key))

  return (
    <>
      <PageHeader title="Specialist Attention"
        subtitle="Who needs your attention, and why. Order follows the AI's provisional routing; your signed decision sets the next action."
        actions={<><Button variant="secondary" icon={RefreshCcw} onClick={() => { void load() }}>Refresh</Button><Button icon={Upload} onClick={() => navigate('/new')}>New screening</Button></>} />

      {error && <Alert tone="danger" title="Could not load Specialist Attention" action={<Button variant="secondary" onClick={() => { void load() }}>Try again</Button>}>{error}</Alert>}

      {data && !data.calibration.available && (
        <div className="mb-4"><Alert tone="info" title="Calibration pending for this grader">
          Probabilities and confidence appear once the calibration job has run for the current grader. Each case still shows why it is in its queue.
        </Alert></div>
      )}
      {data?.reanalysis && data.reanalysis.done < data.reanalysis.total && (
        <div className="mb-4"><Alert tone="info" title="Updating cases to the current models">
          {data.reanalysis.done} of {data.reanalysis.total} stored cases re-analysed. Signed decisions are not changed by re-analysis.
        </Alert></div>
      )}

      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <Tabs value={tab} onChange={value => { setTab(value as Queue | 'all'); navigate('/worklist?tab=' + value + (query ? '&q=' + encodeURIComponent(query) : '')) }}
          tabs={QUEUES.map((q) => ({ value: q.value, label: q.label, count: data ? counts[q.value] ?? 0 : undefined }))} />
        <div className="relative w-full md:w-[280px]">
          <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
          <Input aria-label="Search by patient or case ID" placeholder="Search patient or case ID" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-10" />
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><p className="text-caption text-text-muted" role="status">{data ? rows.length + ' case' + (rows.length === 1 ? '' : 's') + ' in this view' : 'Loading cases…'}</p><Button compact variant="ghost" aria-pressed={details} onClick={() => setDetails(v => !v)}>{details ? 'Hide AI detail columns' : 'Show AI detail columns'}</Button></div>
      {!data && !error && (
        <div className="rounded-card border border-border-default bg-surface-card p-4">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="mb-3 h-8 w-full" />)}
        </div>
      )}
      {data && rows.length === 0 && (
        <div className="rounded-card border border-border-default bg-surface-card">
          <EmptyState icon={Inbox} title={query ? 'No matching cases' : tab === 'signed' ? 'No signed decisions yet' : 'Nothing in this queue'}
            body={query ? 'Check the patient or case ID.' : data.cases.length ? 'Other queues may still need attention.' : 'Upload fundus photographs to start a screening.'}
            action={!query && !data.cases.length && <Button icon={Upload} onClick={() => navigate('/new')}>New screening</Button>} />
        </div>
      )}
      {signError && <div className="mb-4"><Alert tone="danger" title="Some decisions could not be confirmed">{signError}</Alert></div>}
      {tab === 'routine' && routinePile.length > 0 && (
        <div className="mb-4 flex flex-wrap items-end gap-4 rounded-card border border-border-default bg-surface-card p-5 shadow-card">
          <div className="min-w-[240px] flex-1">
            <p className="text-body font-medium">Batch sign-off · {routinePile.length} case{routinePile.length === 1 ? '' : 's'} in this view</p>
            <p className="mt-1 text-caption text-text-secondary">
              The AI found no referable diabetic retinopathy in these gradable images. Signing records <b>your</b> decision, "Routine rescreening", for each photograph under your name. A visit becomes routine only when both eyes are signed routine.
            </p>
            <div className="mt-3"><Checkbox checked={confirmed} onChange={setConfirmed} label="I have reviewed these photographs and agree with routine rescreening for each." /></div>
          </div>
          <Button onClick={signOff} state={signing ? 'loading' : confirmed ? 'default' : 'disabled'}>{signing ?? `Sign ${routinePile.length} decision${routinePile.length === 1 ? '' : 's'}`}</Button>
        </div>
      )}
      {data && rows.length > 0 && (
        <>
          <Table caption="Specialist Attention" columns={columns} rows={rows.slice((current - 1) * PER_PAGE, current * PER_PAGE)} rowKey={(c) => c.id}
            onRowClick={(c) => navigate(`/cases/${c.id}`)} />
          {pages > 1 && <div className="mt-3"><Pagination page={current} pages={pages} total={rows.length} perPage={PER_PAGE} onPage={setPage} /></div>}
        </>
      )}
      <p className="mt-3 text-caption text-text-muted">
        AI routing is provisional: it orders this list and never sets a patient's next action. {settings ? `Operating point: ${settings.wording}.` : ''}
      </p>
      {data?.cases.some((c) => isValidation(c.source)) && (
        <p className="mt-2 text-caption text-text-muted">
          Example cases are validation images (IDRiD-val, APTOS-val), chosen at random by stage with a fixed seed. The models never trained on them and nothing was tuned on the cases shown.
          {agreement?.idrid_val && agreement.aptos_val && ` Across all validation images, the AI’s stage is within one stage of the specialist’s grade for ${pct(agreement.idrid_val.point.within_one)} (IDRiD-val) and ${pct(agreement.aptos_val.point.within_one)} (APTOS-val), and exactly the same for ${pct(agreement.idrid_val.point.accuracy)} and ${pct(agreement.aptos_val.point.accuracy)}.`}
        </p>
      )}
    </>
  )
}

/** OD/OS completeness of the visit this photo belongs to. Older single photos say so instead of guessing a pair. */
function Completeness({ c }: { c: CaseRow }) {
  if (!c.completeness) return <span className="text-caption text-text-muted">Single photo · no visit pairing recorded</span>
  const missing = (['right', 'left'] as const).filter((e) => !c.completeness![e])
  return (
    <span className={cn('text-caption', missing.length ? 'font-medium text-status-warning-text' : 'text-text-muted')}>
      {missing.length ? `${missing.map((e) => (e === 'right' ? 'Right' : 'Left')).join(' and ')} eye missing · incomplete` : 'Both eyes captured'}
    </span>
  )
}
