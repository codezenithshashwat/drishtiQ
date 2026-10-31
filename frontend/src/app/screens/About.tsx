import { useEffect, useState, type ReactNode } from 'react'
import { Alert, Badge, Card, KeyValue, Segmented, Skeleton, Tooltip, cn } from '../../design/components'
import { api, type Agreement, type GradeMetrics, type ModelCard, type Settings } from '../api'
import { STAGE_CLINICAL, num, pct } from '../format'
import { PageHeader } from '../Shell'

const LESIONS = [['MA', 'Microaneurysms'], ['HE', 'Haemorrhages'], ['EX', 'Hard exudates'], ['SE', 'Soft exudates']] as const

export function About() {
  const [m, setM] = useState<ModelCard | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.model().then(setM, (e) => setError(e.message)) }, [])

  if (error) return <Alert tone="danger" title="Could not load the model card">{error}</Alert>
  if (!m) return <div className="flex flex-col gap-4">{['h-[160px]', 'h-[320px]', 'h-[240px]'].map((h) => <Skeleton key={h} className={`${h} w-full`} />)}</div>

  const g = m.grading
  const a2 = m.decisions.a2_ensemble?.verdict.passed ? m.decisions.a2_ensemble : m.decisions.a2_swap
  return (
    <>
      <PageHeader eyebrow="Model card" title="About the model" subtitle={m.version} />
      <div className="flex flex-col gap-6">
        <Alert tone="warning" title="Research prototype for screening decision support">
          Not a diagnosis and not validated for clinical use. Every result needs a qualified clinician’s decision. Development numbers come from held-out
          validation sets. The locked tests (IDRiD clean test, DeepDRiD) were run once on the frozen release candidate rc-1 and are shown separately below;
          Messidor-2 has not been evaluated yet.
        </Alert>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card title="Intended use">
            <ul className="flex list-disc flex-col gap-1 pl-4 text-body text-text-secondary">
              <li>Adults with diabetes, one colour fundus photograph per eye (macula-centred, 45°).</li>
              <li>Suggests an ICDR stage, marks lesions, estimates photographic macular-edema risk and ranks a worklist.</li>
              <li>Defers to a human grader when its calibrated confidence is low or the image quality is poor.</li>
              <li>Not for: children, other retinal diseases, OCT-confirmed macular edema, or use without clinician review.</li>
            </ul>
          </Card>
          <Card title="Models in use">
            <dl className="flex flex-col gap-3">
              {[
                ['Grader', `${m.grader_info.description ?? m.grader}${m.grader_info.members > 1 ? ` (${m.grader_info.members} seeds)` : ''}`],
                ['Grader training data', m.grader_info.train_data],
                ['Lesion segmenter', Object.entries(m.segmenter).map(([k, s]) => `${k}: ${s.model.startsWith('a3:') ? 'A3' : 'v0.1'}`).join(' · ')],
                ['Macular-edema rule', `Hard exudate within 1 disc diameter of the fovea; regions under ${m.dme_rule.min_exudate_area_px} px ignored`],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-caption text-text-secondary">{k}</dt>
                  <dd className="text-body">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>

        <Card title="Grading performance" subtitle="ICDR stage against specialist grades; 95% bootstrap intervals in brackets">
          {m.agreement.idrid_val && m.agreement.aptos_val && <AgreementSummary a={m.agreement.idrid_val} b={m.agreement.aptos_val} />}
          {g.idrid_val && g.aptos_val ? <GradingTable a={g.idrid_val} b={g.aptos_val} /> : <p className="text-body text-text-secondary">No validation run is registered for the current grader.</p>}
          {a2?.splits && (
            <p className="mt-4 text-secondary text-text-secondary">
              Chosen by pre-registered rule ({a2.adr}): against the previous grader, the change in QWK was{' '}
              {Object.entries(a2.splits).map(([s, d], i) => (
                <span key={s}>{i > 0 && '; '}{s.startsWith('idrid') ? 'IDRiD-val' : 'APTOS-val'} {signed(d.delta.qwk.point)} [{signed(d.delta.qwk.ci95[0])}, {signed(d.delta.qwk.ci95[1])}]</span>
              ))}.
            </p>
          )}
        </Card>

        <Card title="Models we compared" subtitle="Same training data within each pair; quadratic weighted kappa on the validation sets (registry)">
          <T head={['Model', 'Training', 'IDRiD-val', 'APTOS-val', 'Decision']} rows={m.compared.map((c) => [
            <span className="font-medium text-text-primary">{c.model}</span>, c.setting,
            c.idrid_val ? c.idrid_val.qwk.toFixed(3) : '—', c.aptos_val ? c.aptos_val.qwk.toFixed(3) : '—',
            <span className="block max-w-[360px] text-left text-secondary">{c.decision} <span className="text-text-muted">({c.ref})</span></span>,
          ])} />
        </Card>

        <Card title="Benchmarks and external validation" subtitle="Locked sets are evaluated once, after the release candidate is frozen">
          <T label="Benchmarks and external validation datasets" head={['Dataset', 'Role', 'Status']} rows={[
            ['APTOS 2019 (validation split)', 'Named benchmark, held out from training', 'Results above'],
            ['IDRiD clean test (102)', 'Locked internal test', 'Evaluated once on rc-1 (below)'],
            ['DeepDRiD (regular fundus)', 'Locked external test', 'Evaluated once on rc-1 (below)'],
            ['Messidor-2', 'Named benchmark, locked external test', 'Pending locked evaluation'],
          ]} />
        </Card>

        <LockedResults />

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          {g.idrid_val && <Card title="Confusion matrix · IDRiD-val" subtitle="Rows: specialist grade · columns: AI stage"><Confusion m={g.idrid_val.confusion} label="Confusion matrix, IDRiD-val" /></Card>}
          {g.aptos_val && <Card title="Confusion matrix · APTOS-val" subtitle="Rows: specialist grade · columns: AI stage"><Confusion m={g.aptos_val.confusion} label="Confusion matrix, APTOS-val" /></Card>}
        </div>

        <Card title="Calibration, deferral and worklist order" subtitle="Fitted on the grader’s inner hold-out; reported on validation sets (ADR-019, ADR-020)">
          {m.calibration ? <CalibrationTable cal={m.calibration} /> : (
            <Alert tone="info" title="Calibration pending">The calibration job has not yet run for the current grader. Probabilities and deferral appear once it has.</Alert>
          )}
        </Card>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card title="Lesion segmentation" subtitle="Pixel AUPR (IDRiD challenge convention); false-positive regions per grade-0 image">
            <SegTable m={m} />
          </Card>
          <Card title="Macular-edema rule" subtitle={`IDRiD-val, ${m.dme_rule.val.n} images, against IDRiD risk labels`}>
            <KeyValue items={[
              { k: 'High-risk sensitivity', v: pct(m.dme_rule.val.high_risk_sensitivity) },
              { k: 'High-risk PPV', v: pct(m.dme_rule.val.high_risk_ppv) },
              { k: 'No-exudate specificity', v: pct(m.dme_rule.val.no_exudate_specificity) },
              { k: 'Macro-F1 (3 levels)', v: num(m.dme_rule.val.macro_f1) },
            ]} />
            <p className="mt-3 text-caption text-text-muted">Photographic proxy only: true macular edema needs OCT.</p>
          </Card>
        </div>

        {m.coverage && <Coverage c={m.coverage} />}

        {m.experiments.length > 0 && (
          <Card title="What we tested before adding it" subtitle="Pre-registered experiments on development data (ADR-041). Only signals marked adopt may change the routing; none changes it today.">
            <div className="flex flex-col gap-3">
              {m.experiments.map((e) => (
                <div key={e.key} className="flex flex-col gap-1 border-t border-border-subtle pt-3 first:border-t-0 first:pt-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body font-medium">{e.name}</span>
                    <Badge tone={e.verdict === 'adopt' ? 'success' : e.verdict === 'abandon' ? 'neutral' : 'info'}>{e.verdict === 'abandon' ? 'tested, did not help' : e.verdict}</Badge>
                  </div>
                  <p className="max-w-measure text-caption text-text-secondary">{e.question}</p>
                  <p className="max-w-measure text-body text-text-secondary">{e.found}</p>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card title="How the follow-up is suggested">
          <div className="flex max-w-measure flex-col gap-2 text-body text-text-secondary">
            <p>Each eye gets one state, first match wins: ungradable photo → retake (a person grades it after one failed retake); stage 3–4 or exudates near the centre of vision → expedited review; stage 2 → referable; any intake answer, a previous clinician referral, a laterality mismatch, low AI confidence or P(referable) at or above the routine threshold → clinician review with the reason; otherwise routine rescreening eligible. The worse eye decides for the patient; with one eye missing, the screening is incomplete.</p>
            <p>These categories follow the structure of the International Council of Ophthalmology <em>Guidelines for Diabetic Eye Care</em> (2017). Timing follows the local programme. They are suggested by the prototype; the doctor decides.</p>
          </div>
        </Card>

        <Card title="Known limitations">
          <ul className="flex list-disc flex-col gap-1 pl-4 text-body text-text-secondary">
            <li>Stage 1 (mild) is often missed: recall is low on both validation sets (see table). Microaneurysms are tiny and the training labels disagree most here.</li>
            <li>Validation data come from two public datasets (India); performance on other cameras and populations is unknown.</li>
            <li>The fovea and optic disc are found by image heuristics; when uncertain, the macula ring is dashed and the macular-edema rule is less reliable.</li>
            <li>Grad-CAM shows where the grader looked. It is not a lesion map and can highlight irrelevant areas.</li>
            <li>No external evaluation yet: Messidor-2 will be evaluated once, at the end, under a locked protocol.</li>
          </ul>
        </Card>

        <Card title="Data sources and licences" subtitle="Thank you to the teams who collected, graded and shared these images">
          <T label="Data sources and licences" head={['Dataset', 'Used for', 'Licence']} rows={[
            ['IDRiD (Porwal et al., 2018; IEEE DataPort)', 'Grading training and validation; lesion masks', 'CC BY 4.0'],
            ['APTOS 2019 Blindness Detection (Kaggle)', 'Grading training and validation', 'Kaggle competition rules'],
            ['MMRDR colour fundus subset (Tang et al., Sci Data 2026)', 'Grading training', 'CC BY 4.0'],
            ['DDR (Li et al., 2019)', 'Lesion-segmentation training; quality-gate check', 'CC BY-NC-SA 4.0 (non-commercial)'],
          ]} />
          <p className="mt-3 text-caption text-text-muted">Because DDR is licensed for non-commercial use only, this prototype is for research and education. The external Messidor-2 evaluation has not been run yet.</p>
        </Card>

        <Card title="Version and checkpoints" subtitle="SHA-256 of every file the app loads">
          <table className="w-full text-secondary">
            <caption className="sr-only">Checkpoint hashes</caption>
            <tbody>
              {Object.entries(m.checkpoints).map(([k, v]) => (
                <tr key={k} className="border-b border-border-default last:border-0">
                  <td className="py-2 pr-4">{k}</td><td className="py-2 text-right font-mono text-caption text-text-secondary">{v.slice(0, 16)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
          {m.history.length > 0 && (
            <p className="mt-3 text-caption text-text-muted">Previous configurations: {m.history.map((h) => `${h.grader ?? 'segmenter'} (replaced ${h.replaced.slice(0, 10)}, ${h.reason})`).join('; ')}.</p>
          )}
        </Card>
      </div>
    </>
  )
}

/** A plain value whose exact figure and 95% interval appear on hover or focus. */
function Exact({ v, ci, source }: { v: number; ci: [number, number]; source: string }) {
  return (
    <Tooltip content={<>{v.toFixed(4)} (95% CI {ci[0].toFixed(3)}–{ci[1].toFixed(3)}) · {source}</>}>
      <span tabIndex={0} className="font-semibold text-text-primary underline decoration-dotted underline-offset-2">{pct(v)}</span>
    </Tooltip>
  )
}

function AgreementSummary({ a, b }: { a: Agreement; b: Agreement }) {
  const line = (label: string, k: keyof Agreement['point']) => (
    <li>{label}: <Exact v={a.point[k]} ci={a.ci95[k]} source={a.run_id} /> of IDRiD-val and <Exact v={b.point[k]} ci={b.ci95[k]} source={b.run_id} /> of APTOS-val images.</li>
  )
  return (
    <ul className="mb-4 flex max-w-measure list-disc flex-col gap-1 pl-4 text-body text-text-secondary">
      {line('The AI’s stage is within one stage of the specialist’s grade for', 'within_one')}
      {line('It gives exactly the specialist’s stage for', 'accuracy')}
      {line('It flags as needing a specialist (stage 2 or worse) the referable cases in', 'referable_sens')}
      {line('It does not flag as referable the non-referable cases in', 'referable_spec')}
    </ul>
  )
}

const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`
const ci = (m: GradeMetrics, k: string) => (m.ci95?.[k] ? ` [${m.ci95[k][0].toFixed(2)}, ${m.ci95[k][1].toFixed(2)}]` : '')

function T({ head, rows, label }: { head: ReactNode[]; rows: ReactNode[][]; label?: string }) {
  return (
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={label ?? (typeof head[0] === 'string' && head[0] ? `${head[0]} table` : 'Results table')}>
      <table className="w-full text-body">
        <thead><tr className="border-b border-border-default">{head.map((h, i) => (
          <th key={i} scope="col" className={cn('h-control px-3 text-caption font-medium text-text-secondary', i === 0 ? 'text-left' : 'text-right')}>{h}</th>
        ))}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i} className="border-b border-border-default last:border-0">{r.map((c, j) => (
            <td key={j} className={cn('h-control px-3', j === 0 ? 'text-left text-text-secondary' : 'text-right tabular-nums')}>{c}</td>
          ))}</tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function GradingTable({ a, b }: { a: GradeMetrics; b: GradeMetrics }) {
  const row = (label: string, k: keyof GradeMetrics['point'], fmt: (v: number) => string = (v) => v.toFixed(3), withCi = false) =>
    [label, fmt(a.point[k]) + (withCi ? ci(a, k) : ''), fmt(b.point[k]) + (withCi ? ci(b, k) : '')]
  return (
    <T head={['Metric', `IDRiD-val (${a.n})`, `APTOS-val (${b.n})`]} rows={[
      row('Quadratic weighted kappa', 'qwk', undefined, true),
      row('Macro-F1', 'macro_f1', undefined, true),
      row('Accuracy', 'accuracy', (v) => pct(v)),
      ...[0, 1, 2, 3, 4].map((i) => row(`Recall, stage ${i} (${STAGE_CLINICAL[i]})`, `recall_g${i}` as keyof GradeMetrics['point'], (v) => pct(v))),
      row('Referable DR sensitivity', 'referable_sens', (v) => pct(v)),
      row('Referable DR specificity', 'referable_spec', (v) => pct(v)),
      row('Severe under-grading (3–4 called 0–1)', 'severe_under', (v) => pct(v, 1)),
      ['Seconds per image (GPU)', num(a.seconds_per_image), num(b.seconds_per_image)],
    ]} />
  )
}

function Confusion({ m, label }: { m: number[][]; label: string }) {
  return (
    <T label={label} head={[<span className="sr-only">Specialist grade</span>, ...[0, 1, 2, 3, 4].map((i) => `AI ${i}`)]} rows={m.map((r, i) => [`Grade ${i}`, ...r.map((v, j) => (
      <span className={cn(i === j && 'font-semibold text-text-primary', i !== j && v === 0 && 'text-text-muted')}>{v}</span>
    ))])} />
  )
}

function CalibrationTable({ cal }: { cal: NonNullable<ModelCard['calibration']> }) {
  const sets = Object.entries(cal.validation)
  const col = (f: (s: (typeof sets)[0][1]) => ReactNode) => sets.map(([, s]) => f(s))
  return (
    <>
      <T label="Calibration, deferral and worklist metrics" head={['Measure', ...sets.map(([k, s]) => `${k.startsWith('idrid') ? 'IDRiD-val' : 'APTOS-val'} (${s.n})`)]} rows={[
        ['ECE of P(referable): uncalibrated → calibrated', ...col((s) => `${s.ece_p_referable.before.toFixed(3)} → ${s.ece_p_referable.after.toFixed(3)}`)],
        ['ECE of stage confidence: raw margin → calibrated', ...col((s) => `${s.ece_stage_confidence.before.toFixed(3)} → ${s.ece_stage_confidence.after.toFixed(3)}`)],
        [`Images the AI grades itself (confidence ≥ ${pct(cal.tau)})`, ...col((s) => pct(s.abstention.coverage))],
        ['Stage accuracy on those images', ...col((s) => pct(s.abstention.accuracy_retained))],
        ['Stage accuracy on deferred images', ...col((s) => pct(s.abstention.accuracy_deferred))],
        ['Stage accuracy without deferral', ...col((s) => pct(s.abstention.accuracy_all))],
        ['Severe under-grading among graded images', ...col((s) => pct(s.abstention.severe_under_retained, 1))],
        ['AUROC for referable DR', ...col((s) => num(s.triage?.auroc, 3))],
        ['Referable cases in the top 20% of the worklist', ...col((s) => pct(s.triage?.referable_in_top20pct))],
        ['Share of worklist read to find 95% of referable cases', ...col((s) => <>{pct(s.triage?.workload_to_95pct_sensitivity)} <span className="text-text-muted">(random order: 95%)</span></>)],
      ]} />
      <p className="mt-3 text-caption text-text-muted">Calibration fitted on {cal.fitted_on} ({cal.created.slice(0, 16).replace('T', ' ')}). Deferral threshold chosen there as the lowest confidence giving ≥85% accuracy on graded images.</p>
    </>
  )
}

function SegTable({ m }: { m: ModelCard }) {
  const models = Object.entries(m.segmentation)
  const get = (r: Record<string, string> | null, k: string) => (r && r[k] !== '' ? Number(r[k]).toFixed(3) : '—')
  return (
    <>
      {models.map(([name, s]) => (
        <div key={name} className="mb-4 last:mb-0">
          <p className="mb-2 flex items-center gap-2 text-secondary font-medium">{name.startsWith('a3:') ? 'A3 segmenter' : 'v0.1 segmenter'} <Badge>{name.split('+').pop()}</Badge></p>
          <T head={['Lesion', 'IDRiD-val AUPR', 'DDR-test AUPR', 'FP regions, grade 0']} rows={LESIONS.map(([k, label]) => [
            label, get(s.idrid_seg_val, `aupr_${k}`), get(s.ddr_seg_test, `aupr_${k}`), get(s.idrid_seg_val, `fp_regions_g0_${k}`),
          ])} />
        </div>
      ))}
    </>
  )
}


function Coverage({ c }: { c: NonNullable<ModelCard['coverage']> }) {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.settings().then(setSettings, (e) => setError(e.message)) }, [])
  const save = (v: string) => api.saveSettings(Number(v)).then(setSettings, (e) => setError(e.message))
  const level = String(settings?.target ?? c.target)
  return (
    <Card title="AI-assisted prioritisation with a routine-rescreening pile"
      subtitle="Policy (c): quality gate passes, AI stage confidence ≥ τ and P(referable) below a threshold fitted on the internal hold-out (ADR-039/040)">
      <div className="flex flex-col gap-4">
        <Alert tone="info" title={`Operating point: ${settings?.wording ?? c.wording}`}>
          Development data only, per image. Patient-level routing and the headline claim wait for the locked DeepDRiD patient-level evaluation.
          {!c.valid && ' Routine routing is switched off: the model in use is not the pinned grader the thresholds were fitted for.'}
        </Alert>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-body font-medium">Target referable miss rate</span>
          <Segmented label="Target referable miss rate" value={level} onChange={save}
            options={Object.keys(c.thresholds).map((k) => ({ value: k, label: `${Number(k) * 100}%${k === '0.025' ? ' (default)' : ''}` }))} />
          {error && <span className="text-caption text-status-danger-text">{error}</span>}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-body">
            <thead className="text-caption text-text-secondary"><tr>
              <th className="py-1 pr-4 font-medium">Set (images)</th><th className="py-1 pr-4 font-medium">Routed to routine [95% CI]</th>
              <th className="py-1 pr-4 font-medium">Referable routed to routine</th><th className="py-1 font-medium">Exact 95% upper bound</th>
            </tr></thead>
            <tbody>
              {Object.entries(c.sets).map(([name, lv]) => {
                const v = lv[level]
                return (
                  <tr key={name} className="border-t border-border-subtle">
                    <td className="py-1 pr-4">{name} ({v.units})</td>
                    <td className="py-1 pr-4 tabular-nums">{pct(v.coverage, 1)} [{pct(v.coverage_ci95[0], 1)}–{pct(v.coverage_ci95[1], 1)}]</td>
                    <td className="py-1 pr-4 tabular-nums">{v.missed} of {v.referable}</td>
                    <td className="py-1 tabular-nums">{pct(v.miss_rate_upper95, 1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="text-caption text-text-muted">
          IDRiD-val has {c.rule_of_three['IDRiD-val']?.referable} referable images: too few to verify any miss-rate level (rule of three). Thresholds were never refitted on validation data. Source: registry {c.run_ids.join(', ')}.
        </p>
      </div>
    </Card>
  )
}


type LockedSet = {
  set: string; tag: string; commit: string; n_images: number; n_patients?: number; qwk: number; qwk_ci95: [number, number]
  sensitivity: number; specificity: number; auroc: number
  images: { coverage: number; coverage_ci95: [number, number]; missed: number; referable: number; upper95: number }
  patients?: { coverage: number; coverage_ci95: [number, number]; missed: number; referable: number; upper95: number }
  quality_agreement?: number; quality_flag_rate_among_poor?: number
}

/** Locked evaluation of rc-1 (ADR-043/046): run once, reported as measured, kept apart from the development numbers. */
function LockedResults() {
  const [d, setD] = useState<{ sets: Record<string, LockedSet> } | null>(null)
  useEffect(() => { fetch('/locked_results.json').then((r) => (r.ok ? r.json() : null)).then(setD, () => setD(null)) }, [])
  if (!d || !Object.keys(d.sets).length) return null
  const rows = Object.values(d.sets)
  const ci = (v: [number, number], digits = 1) => `[${pct(v[0], digits)}–${pct(v[1], digits)}]`
  return (
    <Card title="Locked evaluation of the release candidate (run once)"
      subtitle={`Frozen system rc-1 (commit ${rows[0].commit}); nothing was changed after these results. Development numbers above are not comparable one-to-one.`}>
      <div className="flex flex-col gap-4">
        <T label="Locked evaluation results" head={['Set', 'Agreement (QWK)', 'Referable sens. / spec.', 'Routed to routine at 2.5%', 'Referable routed to routine']} rows={rows.map((r) => [
          <span key="s" className="block text-left">{r.set}<span className="block text-caption text-text-muted">{r.n_images} images{r.n_patients ? `, ${r.n_patients} patients` : ''}</span></span>,
          `${r.qwk.toFixed(3)} [${r.qwk_ci95[0].toFixed(2)}–${r.qwk_ci95[1].toFixed(2)}]`,
          `${pct(r.sensitivity, 1)} / ${pct(r.specificity, 1)}`,
          <span key="c">{pct(r.images.coverage, 1)} of images {ci(r.images.coverage_ci95)}{r.patients && <span className="block">{pct(r.patients.coverage, 1)} of patients {ci(r.patients.coverage_ci95)}</span>}</span>,
          <span key="m">{r.images.missed} of {r.images.referable} images (upper bound {pct(r.images.upper95, 1)}){r.patients && <span className="block">{r.patients.missed} of {r.patients.referable} patients (upper bound {pct(r.patients.upper95, 1)})</span>}</span>,
        ])} />
        <Alert tone="warning" title="What the locked tests show">
          On the IDRiD clean test the routine pile missed {d.sets.idrid_test?.images.missed} of {d.sets.idrid_test?.images.referable} referable images
          (upper bound {pct(d.sets.idrid_test?.images.upper95, 1)}), above the 2.5% target; one of them was grade 3, and all were confident stage-0 calls that the
          confidence check cannot catch. On DeepDRiD no referable patient was routed to routine, but only {pct(d.sets.deepdrid?.patients?.coverage, 1)} of patients
          were routed there. The quality check agrees with DeepDRiD's own quality labels for {pct(d.sets.deepdrid?.quality_agreement, 1)} of images.
          Selective routing is therefore not claimed as validated.
        </Alert>
      </div>
    </Card>
  )
}
