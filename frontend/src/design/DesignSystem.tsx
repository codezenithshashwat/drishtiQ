/* Hidden route /design-system: every foundation and component with its states, for design review. No motion. */
import {
  ArrowRight, Calendar, ClipboardList, Eye, FileText, Inbox, Info, Search, Trash2, Upload, ZoomIn,
} from 'lucide-react'
import { useState } from 'react'
import tokens from '../../../design/tokens.json'
import {
  Alert, Avatar, Badge, Breadcrumb, Button, Card, Checkbox, ConfidenceBadge, EmptyState, Field, Input, KeyValue, ModalPanel,
  Pagination, Popover, PopoverPanel, Progress, Segmented, Select, Skeleton, StageBadge, Switch, Table, Tabs, Toast, Tooltip, TooltipPanel, cn, type State,
} from './components'
import './ds.css'

const STATES: State[] = ['default', 'hover', 'focus', 'active', 'disabled', 'loading']
const STAGES = ['No diabetic damage seen by the AI', 'Early signs', 'Moderate damage', 'Severe damage', 'Advanced disease']
const LESIONS = [['MA', 'Tiny vessel bulges'], ['HE', 'Bleeding spots'], ['EX', 'Yellow deposits'], ['SE', 'Cotton-wool spots']] as const

function lum(hex: string) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

function Section({ id, title, note, children }: { id: string; title: string; note?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="border-t border-border-default py-8">
      <h2 className="text-section font-semibold">{title}</h2>
      {note && <p className="mt-1 max-w-measure text-secondary text-text-secondary">{note}</p>}
      <div className="mt-6">{children}</div>
    </section>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-overline font-medium uppercase text-text-muted">{children}</p>
}

function Swatch({ name, hex, on = '#FFFFFF' }: { name: string; hex: string; on?: string }) {
  return (
    <div className="w-[120px]">
      <div className="h-12 rounded-control border border-border-default" style={{ background: hex }} />
      <p className="mt-1 text-caption font-medium">{name}</p>
      <p className="text-caption text-text-muted">{hex} · {ratio(hex, on).toFixed(1)}:1</p>
    </div>
  )
}

function LayerChip({ label, color, on, state = 'default' }: { label: string; color?: string; on: boolean; state?: State }) {
  return (
    <button aria-pressed={on} className={cn('inline-flex h-control-sm items-center gap-2 rounded-control border px-3 text-secondary font-medium',
      on ? 'border-neutral-400 bg-surface-viewerRaised text-white' : 'border-border-viewer text-neutral-300 hover:text-white hover:border-neutral-500',
      state === 'hover' && !on && 'text-white border-neutral-500', state === 'focus' && 'force-focus')}>
      {color ? <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: color, opacity: on ? 1 : 0.5 }} /> : null}
      {label}
    </button>
  )
}

type Row = { id: string; eye: string; stage: number; risk: string; conf: 'high' | 'moderate' | 'low'; status: string; when: string; regions: number }
const ROWS: Row[] = [
  { id: 'RS-2041', eye: 'L, R', stage: 3, risk: 'High', conf: 'low', status: 'New', when: '12 min ago', regions: 59 },
  { id: 'RS-2040', eye: 'R', stage: 2, risk: 'Possible', conf: 'moderate', status: 'New', when: '40 min ago', regions: 12 },
  { id: 'RS-2038', eye: 'L, R', stage: 4, risk: 'High', conf: 'high', status: 'Reviewed', when: '2 h ago', regions: 87 },
  { id: 'RS-2033', eye: 'L', stage: 1, risk: 'Low', conf: 'high', status: 'Reviewed', when: 'Yesterday', regions: 3 },
  { id: 'RS-2030', eye: 'L, R', stage: 0, risk: 'Low', conf: 'high', status: 'New', when: 'Yesterday', regions: 0 },
]

export default function DesignSystem() {
  const [mode, setMode] = useState<'simple' | 'clinical'>('simple')
  const [tab, setTab] = useState('urgent')
  const c = tokens.color
  return (
    <div className="ds min-h-screen">
      <div className="mx-auto max-w-content px-8 py-8">
        <header className="flex items-end justify-between gap-6 pb-6">
          <div>
            <p className="text-overline font-medium uppercase text-text-muted">RetinaScreen</p>
            <h1 className="mt-1 text-page font-semibold">Design system</h1>
            <p className="mt-1 max-w-measure text-body text-text-secondary">Tokens from <code>design/tokens.json</code>. Every component in every state. Nothing animates: hover and focus change colour or border instantly.</p>
          </div>
          <Segmented label="Wording" value={mode} onChange={setMode} options={[{ value: 'simple', label: 'Simple' }, { value: 'clinical', label: 'Clinical' }]} />
        </header>

        <Section id="colour" title="Colour" note="Neutrals and one brand accent. Severity is always text + colour. Lesion colours (Okabe–Ito) are shown on the viewer surface, the only dark surface. Ratios are contrast against white (or the viewer for lesion colours).">
          <Label>Neutrals</Label>
          <div className="flex flex-wrap gap-4">{Object.entries(c.neutral).map(([k, v]) => <Swatch key={k} name={`neutral ${k}`} hex={v} />)}</div>
          <div className="mt-6 grid grid-cols-2 gap-8">
            <div><Label>Brand (sparingly: primary action, active nav, focus, links)</Label>
              <div className="flex flex-wrap gap-4">{Object.entries(c.brand).map(([k, v]) => <Swatch key={k} name={`brand ${k}`} hex={v} />)}</div></div>
            <div><Label>Text</Label>
              <div className="flex flex-wrap gap-4">{['primary', 'secondary', 'muted', 'link'].map((k) => <Swatch key={k} name={k} hex={(c.text as Record<string, string>)[k]} />)}</div></div>
          </div>
          <div className="mt-6"><Label>Severity — stage 0 to 4 (tint · text · solid)</Label>
            <div className="grid grid-cols-5 gap-4">
              {c.stage.map((s, i) => (
                <div key={i} className="rounded-card border p-3" style={{ background: s.tint, borderColor: s.border }}>
                  <p className="text-secondary font-semibold" style={{ color: s.text }}>Stage {i}</p>
                  <p className="text-caption" style={{ color: s.text }}>{STAGES[i]} · {ratio(s.text, s.tint).toFixed(1)}:1</p>
                  <div className="mt-2 h-2 rounded-full" style={{ background: s.solid }} />
                </div>
              ))}
            </div>
          </div>
          <div className="mt-6 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-8">
            <div><Label>Status</Label>
              <div className="flex flex-wrap gap-2">{(['info', 'warning', 'danger', 'success'] as const).map((t) => <Badge key={t} tone={t}>{t[0].toUpperCase() + t.slice(1)}</Badge>)}</div></div>
            <div><Label>Lesion overlays on the viewer surface</Label>
              <div className="flex flex-wrap gap-4 rounded-card bg-surface-viewer p-4">
                {LESIONS.map(([k, name]) => (
                  <div key={k} className="flex items-center gap-2 text-secondary text-neutral-300">
                    <span className="h-3 w-3 rounded-[3px]" style={{ background: (c.lesion as Record<string, string>)[k] }} />
                    {name} <span className="text-caption text-neutral-400">{ratio((c.lesion as Record<string, string>)[k], c.surface.viewer).toFixed(1)}:1</span>
                  </div>
                ))}
              </div></div>
          </div>
        </Section>

        <Section id="type" title="Typography" note="Inter, tabular numbers, weights 400/500/600, sentence case. Overline labels are the only uppercase text.">
          <div className="grid grid-cols-[160px_minmax(0,1fr)] items-baseline gap-y-3">
            {[['Stage number · 28/600', 'text-stage font-semibold', 'Stage 3'], ['Page title · 20/600', 'text-page font-semibold', 'Worklist'],
              ['Section title · 16/600', 'text-section font-semibold', 'Why this stage'], ['Body · 14/400', 'text-body', 'We found 20 bleeding spots in 4 of 4 areas of the retina.'],
              ['Secondary · 13/400', 'text-secondary text-text-secondary', 'Uploaded 12 min ago · left eye'], ['Caption · 12/400', 'text-caption text-text-muted', 'Model v0.2 · research prototype'],
              ['Overline · 11/500', 'text-overline font-medium uppercase text-text-muted', 'Stage of eye damage']].map(([k, cls, ex]) => (
              <div key={k} className="contents"><span className="text-caption text-text-muted">{k}</span><span className={cls}>{ex}</span></div>
            ))}
          </div>
        </Section>

        <Section id="space" title="Spacing, radius, elevation" note="4 px grid; only 4, 8, 12, 16, 24, 32, 48, 64. Depth comes from 1 px borders; the single shadow is for popovers, toasts and modals.">
          <div className="flex items-end gap-6">
            {Object.entries(tokens.space).map(([k, v]) => (
              <div key={k} className="text-center"><div className="bg-brand-100" style={{ width: v, height: v }} /><p className="mt-1 text-caption text-text-muted">{v}</p></div>
            ))}
            <div className="ml-12 flex gap-6">
              <div className="h-12 w-24 rounded-control border border-border-strong bg-surface-card" /><div className="h-12 w-24 rounded-card border border-border-strong bg-surface-card" />
              <div className="h-12 w-24 rounded-card border border-border-default bg-surface-card shadow-overlay" />
            </div>
            <p className="text-caption text-text-muted">control 6 · card 8 · overlay shadow</p>
          </div>
        </Section>

        <Section id="buttons" title="Buttons" note="Heights 36 (default) and 32 (compact). Icon 16 px with a text label.">
          <div className="grid grid-cols-[120px_repeat(6,minmax(0,1fr))] items-center gap-x-4 gap-y-4">
            <span />{STATES.map((s) => <span key={s} className="text-caption text-text-muted">{s}</span>)}
            {(['primary', 'secondary', 'ghost', 'destructive'] as const).map((v) => (
              <div key={v} className="contents">
                <span className="text-secondary font-medium">{v}</span>
                {STATES.map((s) => (
                  <div key={s}><Button variant={v} state={s} icon={v === 'destructive' ? Trash2 : v === 'primary' ? ArrowRight : undefined}>
                    {v === 'destructive' ? 'Remove' : v === 'primary' ? 'Analyse' : 'Change stage'}</Button></div>
                ))}
              </div>
            ))}
          </div>
          <div className="mt-6 flex items-center gap-2"><Button compact icon={Upload}>Upload</Button><Button compact variant="secondary" icon={FileText}>Create report</Button>
            <Button compact variant="ghost" icon={ZoomIn}>Zoom in</Button></div>
        </Section>

        <Section id="forms" title="Form controls">
          <div className="grid grid-cols-5 gap-6">
            {(['default', 'hover', 'focus', 'disabled'] as State[]).map((s) => (
              <Field key={s} id={`in-${s}`} label={`Case ID (${s})`} hint="Optional. Letters and numbers."><Input id={`in-${s}`} state={s} placeholder="e.g. RS-2041" /></Field>
            ))}
            <Field id="in-err" label="Case ID (invalid)" error="Use letters, numbers and dashes only."><Input id="in-err" invalid defaultValue="RS 20/41" /></Field>
          </div>
          <div className="mt-6 grid grid-cols-5 gap-6">
            <Field id="sel" label="Eye"><Select id="sel"><option>Left eye</option><option>Right eye</option></Select></Field>
            <Field id="sel-d" label="Eye (disabled)"><Select id="sel-d" state="disabled"><option>Left eye</option></Select></Field>
            <div className="col-span-3 flex items-end gap-6">
              <Field id="search" label="Search"><div className="relative w-[240px]"><Search size={16} strokeWidth={1.75} className="absolute left-3 top-3 text-text-muted" aria-hidden /><Input id="search" placeholder="Search case ID" className="pl-8" /></div></Field>
              <div className="flex flex-col gap-1"><span className="text-secondary font-medium">Date</span><Button variant="secondary" icon={Calendar}>Last 7 days</Button></div>
            </div>
          </div>
          <div className="mt-8 grid grid-cols-3 gap-8">
            <div><Label>Segmented control</Label><div className="flex flex-col items-start gap-3">
              {(['default', 'hover', 'focus', 'disabled'] as State[]).map((s) => <Segmented key={s} label={s} state={s} value="simple" options={[{ value: 'simple', label: 'Simple' }, { value: 'clinical', label: 'Clinical' }]} />)}
            </div></div>
            <div><Label>Toggle switch</Label><div className="flex flex-col gap-3">
              <Switch checked label="Show heatmap" /><Switch checked={false} label="Show areas" /><Switch checked={false} state="hover" label="Hover" />
              <Switch checked state="focus" label="Focus" /><Switch checked state="disabled" label="Disabled" />
            </div></div>
            <div><Label>Checkbox</Label><div className="flex flex-col gap-3">
              <Checkbox checked label="Selected" /><Checkbox checked={false} label="Not selected" /><Checkbox checked={false} indeterminate label="Some selected" />
              <Checkbox checked={false} state="hover" label="Hover" /><Checkbox checked state="focus" label="Focus" /><Checkbox checked state="disabled" label="Disabled" />
            </div></div>
          </div>
        </Section>

        <Section id="viewer" title="Viewer toolbar chips" note="Layer toggles inside the dark viewer: colour dot + plain label. Off chips dim their dot.">
          <div className="flex flex-wrap items-center gap-2 rounded-card bg-surface-viewer p-4">
            {LESIONS.map(([k, name], i) => <LayerChip key={k} label={name} color={(c.lesion as Record<string, string>)[k]} on={i !== 3} />)}
            <LayerChip label="Where the AI looked" color={c.heatmap.low} on={false} state="hover" />
            <LayerChip label="Areas" on={false} /><LayerChip label="Centre of vision" on state="focus" />
            <span className="mx-2 h-6 w-px bg-border-viewer" />
            <LayerChip label="Fit" on={false} /><LayerChip label="Original" on={false} />
          </div>
        </Section>

        <Section id="nav" title="Tabs, breadcrumb, pagination">
          <Tabs value={tab} onChange={setTab} forceHover="routine" tabs={[{ value: 'urgent', label: 'Urgent', count: 3 }, { value: 'review', label: 'Needs review', count: 8 },
            { value: 'routine', label: 'Routine', count: 21 }, { value: 'routine-pile', label: 'Routine rescreening eligible', count: 46 }]} />
          <div className="mt-6 flex items-center justify-between"><Breadcrumb items={['Worklist', 'Urgent', 'Case RS-2041']} /></div>
          <div className="mt-6"><Pagination page={2} pages={4} total={78} perPage={20} /></div>
        </Section>

        <Section id="badges" title="Badges" note="Stage badges carry the stage number and plain name; status chips use pills; confidence always has an icon and words.">
          <div className="flex flex-wrap gap-2">{STAGES.map((s, i) => <StageBadge key={i} stage={i} label={s} />)}</div>
          <div className="mt-4 flex flex-wrap items-center gap-2"><Badge pill tone="brand">New</Badge><Badge pill>Reviewed</Badge><Badge pill tone="warning">Needs review</Badge>
            <span className="mx-2 h-6 w-px bg-border-default" /><ConfidenceBadge level="high" /><ConfidenceBadge level="moderate" /><ConfidenceBadge level="low" /></div>
        </Section>

        <Section id="overlays" title="Tooltip, popover, modal, toast" note="Shown open for review. Tooltips and popovers use the single overlay shadow.">
          <div className="flex items-start gap-16">
            <div>
              <Label>Tooltip (hover or focus)</Label>
              <div className="flex flex-col items-start gap-2">
                <TooltipPanel>How closely the AI's stages match specialist grades (1 = perfect). Exact: QWK 0.80.</TooltipPanel>
                <Tooltip content="How closely the AI's stages match specialist grades (1 = perfect). Exact: QWK 0.80.">
                  <button className="inline-flex items-center gap-1 text-body underline decoration-dotted underline-offset-2">Agreement with eye specialists <Info size={16} strokeWidth={1.75} aria-hidden /></button>
                </Tooltip>
              </div>
            </div>
            <div>
              <Label>Popover (click)</Label>
              <div className="flex flex-col items-start gap-2">
                <Popover trigger={<Button variant="secondary" icon={Eye}>Layers</Button>}><span>Layers</span></Popover>
                <PopoverPanel>
                  <p className="text-body font-semibold">Show on image</p>
                  <div className="mt-3 flex flex-col gap-2">{LESIONS.map(([k, name]) => <Checkbox key={k} checked label={name} swatch={(c.lesion as Record<string, string>)[k]} />)}</div>
                </PopoverPanel>
              </div>
            </div>
          </div>
          <div className="mt-8 flex items-start gap-8">
            <ModalPanel title="Change stage" description="Your stage replaces the AI's stage in the report. The reason is saved locally."
              footer={<><Button variant="secondary">Cancel</Button><Button>Save stage</Button></>}>
              <div className="flex flex-col gap-4">
                <Field id="m-stage" label="Stage"><Select id="m-stage" defaultValue="2"><option value="2">Stage 2 · Moderate damage</option></Select></Field>
                <Field id="m-reason" label="Reason" hint="A short note for the record."><Input id="m-reason" placeholder="e.g. haemorrhages fewer than the AI counted" /></Field>
              </div>
            </ModalPanel>
            <div className="flex flex-col gap-3"><Toast title="Stage confirmed for RS-2041." action={<Button variant="ghost" compact>Undo</Button>} />
              <Toast tone="warning" title="Image quality may be too low." /><Toast tone="danger" title="Upload failed. The file is not an image." /></div>
          </div>
        </Section>

        <Section id="feedback" title="Alerts, empty state, loading" note="Inline alerts say what happened and what to do. Loading uses static skeletons.">
          <div className="grid grid-cols-2 gap-4">
            <Alert tone="info" title="Every number comes from this photo.">Tap a sentence to see where it is on the image.</Alert>
            <Alert tone="warning" title="Low confidence: needs a doctor's look." action={<Button compact variant="secondary">Review image</Button>}>The AI is unsure between Stage 2 and Stage 3.</Alert>
            <Alert tone="danger" title="This photo cannot be analysed.">No retina was found. Upload a colour fundus photograph.</Alert>
            <Alert tone="success" title="Stage confirmed.">Signed off by you just now.</Alert>
          </div>
          <div className="mt-6 grid grid-cols-3 gap-4">
            <Card><EmptyState icon={Inbox} title="No urgent cases" body="Cases at Stage 3 or 4, or with high central-vision risk, will appear here." action={<Button compact icon={Upload}>New screening</Button>} /></Card>
            <Card title={<Skeleton className="h-4 w-32" />}><div className="flex flex-col gap-3"><Skeleton className="h-6 w-40" /><Skeleton className="h-2 w-full" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-3/4" /></div></Card>
            <Card title="Image quality" subtitle="Heuristic checks, not a validated gradability model" footer={<Button compact variant="ghost">Details</Button>}>
              <KeyValue items={[{ k: 'Field of view', v: 'Found' }, { k: 'Sharpness', v: '3.4' }, { k: 'Brightness', v: '64' }, { k: 'Centre of vision', v: <Badge tone="success">Found</Badge> }]} />
              <div className="mt-4"><Progress value={62} label="Analysing 5 of 8 images" /></div>
            </Card>
          </div>
        </Section>

        <Section id="table" title="Table" note="Sticky header, row hover tint, selected row, numbers right-aligned.">
          <Table<Row> caption="Worklist sample" rowKey={(r) => r.id} selectable selected={new Set(['RS-2040'])} hovered="RS-2038" maxHeight={320} onRowClick={() => {}}
            rows={ROWS} columns={[
              { key: 'thumb', header: '', width: '64px', render: () => <span className="block h-8 w-8 rounded-control bg-surface-viewer" aria-hidden /> },
              { key: 'id', header: 'Case', render: (r) => <span className="font-medium">{r.id}</span> },
              { key: 'eye', header: 'Eyes', render: (r) => r.eye },
              { key: 'stage', header: 'Stage', render: (r) => <StageBadge stage={r.stage} label={STAGES[r.stage]} /> },
              { key: 'risk', header: 'Central-vision risk', render: (r) => r.risk },
              { key: 'conf', header: 'Confidence', render: (r) => <ConfidenceBadge level={r.conf} /> },
              { key: 'regions', header: 'Lesion regions', numeric: true, render: (r) => r.regions },
              { key: 'status', header: 'Status', render: (r) => <Badge pill tone={r.status === 'New' ? 'brand' : 'neutral'}>{r.status}</Badge> },
              { key: 'when', header: 'Uploaded', numeric: true, render: (r) => <span className="text-text-secondary">{r.when}</span> },
            ]} />
        </Section>

        <Section id="misc" title="Avatar, key–value" >
          <div className="flex items-center gap-8"><div className="flex gap-2"><Avatar name="Asha Rao" /><Avatar name="Dev Patel" /></div>
            <div className="w-[320px]"><KeyValue items={[{ k: 'Model', v: 'v0.2' }, { k: 'Images analysed', v: '1,248' }, { k: 'Median time per image', v: '3.1 s' }]} /></div>
            <div className="flex items-center gap-2 text-secondary text-text-secondary"><ClipboardList size={20} strokeWidth={1.75} aria-hidden />Nav icon 20 px</div>
          </div>
        </Section>
      </div>
    </div>
  )
}
