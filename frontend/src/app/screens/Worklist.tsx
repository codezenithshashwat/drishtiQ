import { AlertTriangle, BarChart3, Inbox, ListChecks, RefreshCcw, Search, Upload, type LucideIcon } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, ConfidenceBadge, EmptyState, Input, Pagination, Skeleton, StageBadge, Table, Tabs, cn, type Column } from '../../design/components'
import { api, type CaseRow, type ModelCard, type Settings } from '../api'
import { DME_LABEL, ROUTING, eyeName, STAGE_CLINICAL, isValidation, pct, when } from '../format'
import { href, linkProps, navigate } from '../router'
import { PageHeader } from '../Shell'

type Data = Awaited<ReturnType<typeof api.cases>>
const PER_PAGE = 50

export function Worklist({ initialTab, initialQuery }: { initialTab?: string | null; initialQuery?: string | null }) {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState(initialTab && ['review', 'routine', 'reviewed', 'all'].includes(initialTab) ? initialTab : 'review')
  const [query, setQuery] = useState(initialQuery ?? '')
  const [page, setPage] = useState(1)
  const [agreement, setAgreement] = useState<ModelCard['agreement'] | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [details, setDetails] = useState(false)
  const [signError, setSignError] = useState<string | null>(null)
  const [signer, setSigner] = useState('')
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
      .filter((c) => (tab === 'review' ? c.status === 'new' && c.routing.state !== 'ROUTINE_RESCREEN_ELIGIBLE'
        : tab === 'routine' ? c.status === 'new' && c.routing.state === 'ROUTINE_RESCREEN_ELIGIBLE'
          : tab === 'reviewed' ? c.status === 'reviewed' : true))
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
  useEffect(() => { setPage(1) }, [tab, query])

  const open = data?.cases.filter((c) => c.status === 'new') ?? []
  const count = (...states: string[]) => open.filter((c) => states.includes(c.routing.state)).length
  const counts = data ? { review: open.length - count('ROUTINE_RESCREEN_ELIGIBLE'), routine: count('ROUTINE_RESCREEN_ELIGIBLE'),
    reviewed: data.cases.filter((c) => c.status === 'reviewed').length, all: data.cases.length } : null
  const routinePile = rows.filter((c) => c.status === 'new' && c.routing.state === 'ROUTINE_RESCREEN_ELIGIBLE')

  // Batch sign-off of the routine-rescreening pile: one review ("agree") per case, by a named clinician.
  async function signOff() {
    if (signing || !signer.trim()) return
    setSignError(null)
    let saved = 0
    try {
      for (const c of routinePile) {
        setSigning('Saving review ' + (saved + 1) + ' of ' + routinePile.length)
        await api.review(c.id, { reviewer: signer.trim(), decision: 'agree', corrected_stage: null, corrected_dme: null, note: 'Batch sign-off of the routine-rescreening pile' })
        saved++
      }
    } catch (e) {
      setSignError(saved + ' reviews confirmed saved. ' + (e as Error).message + ' Refresh and check the remaining cases before retrying.')
    } finally {
      setSigning(null)
      await load()
    }
  }

  const allColumns: Column<CaseRow>[] = [
    { key: 'routing', header: 'AI-suggested priority', width: '170px', render: (c) => (
      <span title={c.routing.reasons.join(' ')}><Badge tone={ROUTING[c.routing.state].tone} dot>{ROUTING[c.routing.state].label}</Badge></span>
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
        </div>
      </div>
    ) },
    { key: 'stage', header: 'AI stage', render: (c) => (c.stage == null ? <Badge tone="warning">Not assessable</Badge> : <StageBadge stage={c.stage} label={STAGE_CLINICAL[c.stage]} />) },
    { key: 'pref', header: 'P(referable)', numeric: true, width: '120px', render: (c) => <span className="tabular-nums">{c.assist.available ? pct(c.assist.p_referable) : '—'}</span> },
    { key: 'lesions', header: 'Lesion regions', numeric: true, width: '120px', render: (c) => <span className="tabular-nums">{c.stage == null ? '—' : c.lesion_regions}</span> },
    { key: 'conf', header: 'Confidence', width: '170px', render: (c) => (c.assist.confidence_level ? <ConfidenceBadge level={c.assist.confidence_level} /> : <span className="text-text-muted">—</span>) },
    { key: 'dme', header: 'Macula', width: '90px', render: (c) => (c.dme ? DME_LABEL[c.dme] : '—') },
    { key: 'status', header: 'Status', width: '100px', render: (c) => (c.status === 'reviewed' ? <Badge tone="success">Reviewed</Badge> : <Badge tone="brand">New</Badge>) },
    { key: 'created', header: 'Added', numeric: true, width: '120px', render: (c) => <span className="whitespace-nowrap text-text-secondary tabular-nums">{when(c.created)}</span> },
  ]

  // The status column only adds information on the All tab.
  const columns = allColumns.filter(c => (details || !['lesions', 'conf', 'dme'].includes(c.key)) && (tab === 'all' || c.key !== 'status')).sort((a, b) => a.key === 'patient' ? -1 : b.key === 'patient' ? 1 : 0)

  return (
    <>
      <PageHeader eyebrow="AI-assisted prioritisation" title={tab === 'reviewed' ? 'Review history' : 'Clinical worklist'}
        subtitle="Prioritised by AI-suggested routing. Every case requires clinical judgment."
        actions={<><Button variant="secondary" icon={RefreshCcw} onClick={() => { void load() }}>Refresh</Button><Button icon={Upload} onClick={() => navigate('/new')}>New screening</Button></>} />

      {error && <Alert tone="danger" title="Could not load the worklist" action={<Button variant="secondary" onClick={() => { void load() }}>Try again</Button>}>{error}</Alert>}

      {data && !data.calibration.available && (
        <div className="mb-4"><Alert tone="info" title="Calibration pending for this grader">
          Probabilities and confidence appear once the calibration job has run for the current grader. Review the routing reasons in each case.
        </Alert></div>
      )}
      {data?.reanalysis && data.reanalysis.done < data.reanalysis.total && (
        <div className="mb-4"><Alert tone="info" title="Updating cases to the current models">
          {data.reanalysis.done} of {data.reanalysis.total} stored cases re-analysed. Reload to see the rest.
        </Alert></div>
      )}

      <div className="mb-6 grid grid-cols-2 divide-x divide-border-default rounded-card border border-border-default bg-surface-card lg:grid-cols-4">
        <Stat icon={AlertTriangle} label="Expedited review" value={data ? count('URGENT_REVIEW') : undefined} hint="Suspected severe disease or central-vision concern" />
        <Stat icon={ListChecks} label="Review, refer or retake" value={data ? count('CLINICIAN_REVIEW', 'REFERABLE', 'RETAKE') : undefined} hint="Each with its reason" />
        <Stat icon={RefreshCcw} label="Routine rescreening eligible" value={counts?.routine} hint={settings ? settings.wording : 'Operating point loading'} />
        <Stat icon={BarChart3} label="Eye images" value={counts?.all} hint={counts ? `${counts.reviewed} reviewed by a clinician` : undefined} />
      </div>

      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <Tabs value={tab} onChange={value => { setTab(value); navigate('/worklist?tab=' + value + (query ? '&q=' + encodeURIComponent(query) : '')) }} tabs={[
          { value: 'review', label: 'Needs review', count: counts?.review },
          { value: 'routine', label: 'Routine rescreening', count: counts?.routine },
          { value: 'reviewed', label: 'Reviewed', count: counts?.reviewed },
          { value: 'all', label: 'All', count: counts?.all },
        ]} />
        <div className="relative w-full md:w-[280px]">
          <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
          <Input aria-label="Search by patient or case ID" placeholder="Search patient or case ID" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-10" />
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><p className="text-caption text-text-muted" role="status">{data ? rows.length + ' case' + (rows.length === 1 ? '' : 's') + ' in this view' : 'Loading cases…'}</p><Button compact variant="ghost" aria-pressed={details} onClick={() => setDetails(v => !v)}>{details ? 'Hide additional columns' : 'Show additional columns'}</Button></div>
      {!data && !error && (
        <div className="rounded-card border border-border-default bg-surface-card p-4">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="mb-3 h-8 w-full" />)}
        </div>
      )}
      {data && rows.length === 0 && (
        <div className="rounded-card border border-border-default bg-surface-card">
          <EmptyState icon={Inbox} title={query ? 'No matching cases' : tab === 'review' ? 'Nothing waiting for review' : 'No cases yet'}
            body={query ? 'Check the patient or case ID.' : 'Upload a fundus photograph to start a screening.'}
            action={!query && <Button icon={Upload} onClick={() => navigate('/new')}>New screening</Button>} />
        </div>
      )}
      {signError && <div className="mb-4"><Alert tone="danger" title="Some reviews could not be confirmed">{signError}</Alert></div>}
      {tab === 'routine' && routinePile.length > 0 && (
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-card border border-border-default bg-surface-card p-5 shadow-card">
          <div className="min-w-[240px] flex-1">
            <p className="text-body font-medium">Batch sign-off · {routinePile.length} filtered cases across all pages</p>
            <p className="text-caption text-text-secondary">
              "No referable diabetic retinopathy detected by AI in gradable images." Open any case to check it first; signing records your agreement for each case.
            </p>
          </div>
          <Input aria-label="Reviewer name for batch sign-off" placeholder="Your name or initials" disabled={!!signing} value={signer} onChange={(e) => setSigner(e.target.value)} className="md:w-[220px]" />
          <Button onClick={signOff} state={signing ? 'loading' : signer.trim() ? 'default' : 'disabled'}>{signing ?? `Sign off ${routinePile.length} case${routinePile.length === 1 ? '' : 's'}`}</Button>
        </div>
      )}
      {data && rows.length > 0 && (
        <>
          <Table caption="Screening worklist" columns={columns} rows={rows.slice((current - 1) * PER_PAGE, current * PER_PAGE)} rowKey={(c) => c.id}
            onRowClick={(c) => navigate(`/cases/${c.id}`)} />
          {pages > 1 && <div className="mt-3"><Pagination page={current} pages={pages} total={rows.length} perPage={PER_PAGE} onPage={setPage} /></div>}
        </>
      )}
      {data?.cases.some((c) => isValidation(c.source)) && (
        <p className="mt-3 text-caption text-text-muted">
          Example cases are validation images (IDRiD-val, APTOS-val), chosen at random by stage with a fixed seed. The models never trained on them and nothing was tuned on the cases shown.
          {agreement?.idrid_val && agreement.aptos_val && ` Across all validation images, the AI’s stage is within one stage of the specialist’s grade for ${pct(agreement.idrid_val.point.within_one)} (IDRiD-val) and ${pct(agreement.aptos_val.point.within_one)} (APTOS-val), and exactly the same for ${pct(agreement.idrid_val.point.accuracy)} and ${pct(agreement.aptos_val.point.accuracy)}.`}
        </p>
      )}
    </>
  )
}

function Stat({ icon: Icon, label, value, hint }: { icon: LucideIcon; label: string; value?: number; hint?: string }) {
  return <div className="min-w-0 p-4" title={hint}>
    <div className="mb-2 flex items-center justify-between gap-2"><span className="text-caption text-text-secondary">{label}</span><Icon size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-text-muted" /></div>
    {value === undefined ? <Skeleton className="h-8 w-12" /> : <p className="text-stage font-semibold leading-none tabular-nums">{value}</p>}
    {hint && <p className="sr-only">{hint}</p>}
  </div>
}
