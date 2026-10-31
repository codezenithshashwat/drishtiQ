import { AlertTriangle, BarChart3, Inbox, ListChecks, RefreshCcw, Search, Upload, type LucideIcon } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, ConfidenceBadge, EmptyState, IconCircle, Input, Pagination, Skeleton, StageBadge, Table, Tabs, cn, type Column } from '../../design/components'
import { api, type CaseRow, type ModelCard, type Settings } from '../api'
import { DME_LABEL, ROUTING, eyeName, STAGE_CLINICAL, isValidation, pct, when } from '../format'
import { navigate } from '../router'
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
  const [signer, setSigner] = useState('')
  const [signing, setSigning] = useState<string | null>(null)

  const load = () => api.cases().then(setData, (e) => setError(e.message))
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
    for (const c of routinePile) {
      setSigning(`Signing off ${c.id}…`)
      await api.review(c.id, { reviewer: signer.trim(), decision: 'agree', corrected_stage: null, corrected_dme: null, note: 'Batch sign-off of the routine-rescreening pile' })
    }
    setSigning(null)
    load()
  }

  const allColumns: Column<CaseRow>[] = [
    { key: 'routing', header: 'Routing', width: '170px', render: (c) => (
      <span title={c.routing.reasons.join(' ')}><Badge tone={ROUTING[c.routing.state].tone} dot>{ROUTING[c.routing.state].label}</Badge></span>
    ) },
    { key: 'patient', header: 'Patient', width: '250px', render: (c) => (
      <div className="flex items-center gap-3">
        {c.thumbnail ? <img src={c.thumbnail} alt="" loading="lazy" className="h-12 w-12 rounded-control bg-surface-viewer object-cover" /> : <span className="h-12 w-12 rounded-control bg-neutral-200" />}
        <div className="min-w-0">
          <div className="flex items-center gap-2 whitespace-nowrap font-medium">{c.patient_ref}{isValidation(c.source) && <Badge tone="info">Validation image</Badge>}</div>
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
  const columns = tab === 'all' ? allColumns : allColumns.filter((c) => c.key !== 'status')

  return (
    <>
      <PageHeader eyebrow="AI-assisted prioritisation" title={tab === 'reviewed' ? 'History' : 'Worklist'}
        subtitle="Expedited review first, then clinician review, referable cases and retakes; the routine-rescreening pile last."
        actions={<Button icon={Upload} onClick={() => navigate('/new')}>New screening</Button>} />

      {error && <Alert tone="danger" title="Could not load the worklist">{error}</Alert>}

      {data && !data.calibration.available && (
        <div className="mb-4"><Alert tone="info" title="Calibration pending for this grader">
          Probabilities and confidence appear once the calibration job has run for the current grader. Until then the list is ordered by case age.
        </Alert></div>
      )}
      {data?.reanalysis && data.reanalysis.done < data.reanalysis.total && (
        <div className="mb-4"><Alert tone="info" title="Updating cases to the current models">
          {data.reanalysis.done} of {data.reanalysis.total} stored cases re-analysed. Reload to see the rest.
        </Alert></div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Stat icon={AlertTriangle} label="Expedited review" value={data ? count('URGENT_REVIEW') : undefined} hint="Suspected severe disease or central-vision concern" />
        <Stat icon={ListChecks} label="Clinician review, referable or retake" value={data ? count('CLINICIAN_REVIEW', 'REFERABLE', 'RETAKE') : undefined} hint="Each with its reason" />
        <Stat icon={RefreshCcw} label="Routine rescreening eligible" value={counts?.routine} hint={settings ? settings.wording : 'Operating point loading'} />
        <Stat icon={BarChart3} label="Total screenings" value={counts?.all} hint={counts ? `${counts.reviewed} reviewed by a clinician` : undefined} />
      </div>

      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <Tabs value={tab} onChange={setTab} tabs={[
          { value: 'review', label: 'Needs review', count: counts?.review },
          { value: 'routine', label: 'Routine rescreening', count: counts?.routine },
          { value: 'reviewed', label: 'Reviewed', count: counts?.reviewed },
          { value: 'all', label: 'All', count: counts?.all },
        ]} />
        <div className="relative w-full md:w-[280px]">
          <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
          <Input aria-label="Search by patient or case ID" placeholder="Search patient or case ID" value={query} onChange={(e) => setQuery(e.target.value)} className="rounded-full pl-10" />
        </div>
      </div>

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
      {tab === 'routine' && routinePile.length > 0 && (
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-card border border-border-default bg-surface-card p-5 shadow-card">
          <div className="min-w-[240px] flex-1">
            <p className="text-body font-medium">Batch sign-off</p>
            <p className="text-caption text-text-secondary">
              "No referable diabetic retinopathy detected by AI in gradable images." Open any case to check it first; signing records your agreement for each case.
            </p>
          </div>
          <Input aria-label="Reviewer name for batch sign-off" placeholder="Your name or initials" value={signer} onChange={(e) => setSigner(e.target.value)} className="md:w-[220px]" />
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

function Stat({ icon, label, value, hint }: { icon: LucideIcon; label: string; value?: number; hint?: string }) {
  return (
    <div className="flex gap-4 rounded-card border border-border-default bg-surface-card p-5 shadow-card">
      <IconCircle icon={icon} />
      <div className="min-w-0">
        {value === undefined ? <Skeleton className="h-8 w-12" /> : <p className="font-display text-display-sm leading-none tabular-nums">{value}</p>}
        <p className="mt-1 text-secondary font-medium text-text-primary">{label}</p>
        {hint && <p className="mt-1 text-caption text-text-muted">{hint}</p>}
      </div>
    </div>
  )
}
