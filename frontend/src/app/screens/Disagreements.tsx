import { Download, MessageSquareOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Alert, Button, EmptyState, Skeleton, StageBadge, Table, type Column } from '../../design/components'
import { api, type Disagreement } from '../api'
import { eyeName, STAGE_CLINICAL, when } from '../format'
import { linkProps, navigate } from '../router'
import { PageHeader } from '../Shell'

// Doctor-feedback view: every case where a clinician changed the AI's stage, with the reason. Nothing retrains
// automatically; the export is what a future, pre-registered retraining would start from.
export function Disagreements() {
  const [data, setData] = useState<{ disagreements: Disagreement[]; reviews_total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.disagreements().then(setData, (e) => setError(e.message)) }, [])

  const rows = data?.disagreements ?? []
  const higher = rows.filter((d) => d.ai_stage != null && d.corrected_stage != null && d.ai_stage > d.corrected_stage).length
  const lower = rows.filter((d) => d.ai_stage != null && d.corrected_stage != null && d.ai_stage < d.corrected_stage).length

  const columns: Column<Disagreement>[] = [
    { key: 'case', header: 'Case', render: (d) => (
      <div><a {...linkProps('/cases/' + encodeURIComponent(d.case_id))} className="break-words font-semibold no-underline hover:underline">{d.patient_ref ?? d.case_id}<span className="sr-only">, case {d.case_id}</span></a><div className="text-caption text-text-muted">{d.case_id}{d.eye ? ` · ${eyeName(d.eye)}` : ''}</div></div>
    ) },
    { key: 'ai', header: 'AI stage', render: (d) => (d.ai_stage == null ? '—' : <StageBadge stage={d.ai_stage} label={STAGE_CLINICAL[d.ai_stage]} />) },
    { key: 'doctor', header: 'Clinician stage', render: (d) => (d.corrected_stage == null ? '—' : <StageBadge stage={d.corrected_stage} label={STAGE_CLINICAL[d.corrected_stage]} />) },
    { key: 'reason', header: 'Reason', render: (d) => <span className="block min-w-[160px] max-w-[420px] break-words text-secondary">{d.note || <span className="text-text-muted">No reason given</span>}</span> },
    { key: 'who', header: 'Reviewer', width: '140px', render: (d) => d.reviewer },
    { key: 'when', header: 'When', numeric: true, width: '130px', render: (d) => <span className="whitespace-nowrap text-text-secondary">{when(d.created)}</span> },
  ]

  return (
    <>
      <PageHeader eyebrow="Doctor feedback" title="Disagreements" subtitle="Cases where a clinician changed the AI's stage. The model does not retrain on its own; these reviews are kept for a planned, pre-registered update."
        actions={<Button variant="secondary" icon={Download} onClick={() => { window.location.href = '/api/feedback.csv' }}>Export all reviews (CSV)</Button>} />
      <p className="mb-5 rounded-control bg-surface-subtle p-3 text-caption text-text-secondary">These are recorded clinician assessments, not adjudicated ground truth. Signed decisions set the next action in reports and linked patient status. AI suggestions remain labelled as provisional.</p>
      {error && <Alert tone="danger" title="Could not load the disagreements">{error}</Alert>}
      {!data && !error && <Skeleton className="h-[240px] w-full" />}
      {data && rows.length === 0 && (
        <div className="rounded-card border border-border-default bg-surface-card">
          <EmptyState icon={MessageSquareOff} title="No disagreements yet"
            body={data.reviews_total ? `All ${data.reviews_total} reviews so far agreed with the AI or marked the image ungradable.` : 'Reviews appear here when a clinician changes the AI’s stage in the Case View.'}
            action={<Button variant="secondary" onClick={() => navigate('/worklist')}>Go to the worklist</Button>} />
        </div>
      )}
      {rows.length > 0 && (
        <>
          <p className="mb-4 text-secondary text-text-secondary">
            {rows.length} of {data!.reviews_total} reviews changed the stage: the AI was higher than the clinician in {higher}, lower in {lower}.
          </p>
          <Table caption="Disagreements between clinicians and the AI" columns={columns} rows={rows} rowKey={(d) => String(d.review_id)} onRowClick={(d) => navigate(`/cases/${d.case_id}`)} />
        </>
      )}
    </>
  )
}
