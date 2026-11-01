/* RetinaScreen component library. Built only from token classes (tailwind.config.js <- design/tokens.json).
   Every interactive component accepts `state` so the /design-system gallery can show hover / focus / active /
   disabled / loading side by side; in the app the same styles come from real :hover / :focus-visible / :active. */
import * as RDialog from '@radix-ui/react-dialog'
import * as RPopover from '@radix-ui/react-popover'
import * as RTabs from '@radix-ui/react-tabs'
import * as RTooltip from '@radix-ui/react-tooltip'
import {
  AlertTriangle, Check, ChevronLeft, ChevronRight, CircleAlert, CircleCheck, Info, Loader, Minus, X, type LucideIcon,
} from 'lucide-react'
import { Children, cloneElement, isValidElement, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'

export type State = 'default' | 'hover' | 'focus' | 'active' | 'disabled' | 'loading'
export const cn = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ')
const ICON = { size: 16, strokeWidth: 1.75 }

/* ---------- Button ---------- */
type Variant = 'primary' | 'secondary' | 'ghost' | 'destructive'
const BUTTON: Record<Variant, { base: string; hover: string; hoverable: string; active: string }> = {
  primary: { base: 'bg-cta text-text-onBrand border border-transparent shadow-card', hover: 'bg-cta-hover',
    hoverable: 'hover:bg-cta-hover', active: 'active:bg-cta-hover' },
  secondary: { base: 'bg-surface-card text-text-primary border border-border-strong', hover: 'bg-brand-50',
    hoverable: 'hover:bg-brand-50 hover:border-brand-100', active: 'active:bg-brand-50' },
  ghost: { base: 'bg-transparent text-text-primary border border-transparent', hover: 'bg-brand-50',
    hoverable: 'hover:bg-brand-50', active: 'active:bg-brand-50' },
  destructive: { base: 'bg-surface-card text-status-danger-text border border-status-danger-border', hover: 'bg-status-danger-tint',
    hoverable: 'hover:bg-status-danger-tint', active: 'active:bg-status-danger-tint' },
}

export function Button({ variant = 'primary', compact, icon: Icon, state = 'default', children, className, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; compact?: boolean; icon?: LucideIcon; state?: State }) {
  const v = BUTTON[variant]
  const disabled = state === 'disabled' || state === 'loading' || rest.disabled
  return (
    <button type="button" {...rest} disabled={disabled} aria-busy={state === 'loading' || undefined}
      className={cn('inline-flex items-center justify-center gap-2 rounded-control px-4 text-body font-medium whitespace-nowrap',
        compact ? 'h-control-sm' : 'h-control', v.base, !disabled && v.hoverable, !disabled && v.active,
        state === 'hover' && v.hover, state === 'active' && v.hover, state === 'focus' && 'force-focus',
        disabled && 'opacity-50', className)}>
      {state === 'loading' ? <Loader {...ICON} aria-hidden className="busy-icon" /> : Icon && <Icon {...ICON} aria-hidden />}
      {children}
    </button>
  )
}

/* ---------- Form controls ---------- */
const FIELD = 'h-control w-full rounded-control border bg-surface-card px-3 text-body text-text-primary placeholder:text-text-muted'
const fieldState = (state: State, invalid?: boolean) => cn(
  invalid ? 'border-status-danger-icon' : 'border-border-strong',
  state === 'hover' ? 'border-neutral-400' : 'hover:border-neutral-400',
  state === 'focus' && 'force-focus', state === 'disabled' && 'bg-surface-subtle text-text-muted cursor-not-allowed')

export function Field({ label, hint, error, children, id }: { label: string; hint?: string; error?: string; children: ReactNode; id: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-secondary font-medium text-text-primary">{label}</label>
      {Children.map(children, child => isValidElement<{ id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>(child) ? cloneElement(child, {
        id: child.props.id ?? id,
        'aria-describedby': [child.props['aria-describedby'], error || hint ? `${id}-help` : undefined].filter(Boolean).join(' ') || undefined,
        'aria-invalid': error ? true : child.props['aria-invalid'],
      }) : child)}
      {(error || hint) && <p id={`${id}-help`} role={error ? 'alert' : undefined} className={cn('text-caption', error ? 'text-status-danger-text' : 'text-text-muted')}>{error || hint}</p>}
    </div>
  )
}

export function Input({ state = 'default', invalid, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { state?: State; invalid?: boolean }) {
  return <input {...rest} disabled={state === 'disabled' || rest.disabled} aria-invalid={invalid || rest['aria-invalid'] || undefined}
    className={cn(FIELD, fieldState(state, invalid), className)} />
}

export function Select({ state = 'default', children, className, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { state?: State }) {
  return <select {...rest} disabled={state === 'disabled' || rest.disabled} className={cn(FIELD, 'pr-8', fieldState(state), className)}>{children}</select>
}

export function Segmented<T extends string>({ options, value, onChange, label, state = 'default' }:
  { options: { value: T; label: string }[]; value: T; onChange?: (v: T) => void; label: string; state?: State }) {
  return (
    <div role="radiogroup" aria-label={label} className={cn('inline-flex flex-wrap gap-1 rounded-control border border-border-default bg-surface-subtle p-1',
      state === 'disabled' && 'opacity-50')}>
      {options.map((o, i) => {
        const on = o.value === value
        return (
          <button type="button" key={o.value} role="radio" aria-checked={on} tabIndex={on ? 0 : -1} disabled={state === 'disabled'} onClick={() => onChange?.(o.value)}
            onKeyDown={e => {
              const direction = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
              if (!direction && e.key !== 'Home' && e.key !== 'End') return
              e.preventDefault()
              const next = e.key === 'Home' ? 0 : e.key === 'End' ? options.length - 1 : (i + direction + options.length) % options.length
              onChange?.(options[next].value)
              e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')[next]?.focus()
            }}
            className={cn('min-h-[32px] px-3 py-1 rounded-sm text-secondary font-medium',
              on ? 'bg-surface-card text-brand-800 border border-border-strong shadow-card' : 'text-text-secondary border border-transparent hover:text-text-primary',
              state === 'hover' && !on && i === 1 && 'text-text-primary', state === 'focus' && on && 'force-focus')}>
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Switch({ checked, label, state = 'default', onChange }: { checked: boolean; label: string; state?: State; onChange?: (v: boolean) => void }) {
  const disabled = state === 'disabled'
  return (
    <label className={cn('inline-flex items-center gap-2 text-body', disabled && 'opacity-50')}>
      <button type="button" aria-label={label} role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange?.(!checked)}
        className={cn('relative h-6 w-8 rounded-full border', checked ? 'bg-brand-700 border-brand-700' : 'bg-neutral-200 border-border-strong',
          state === 'hover' && (checked ? 'bg-brand-800' : 'bg-neutral-300'), state === 'focus' && 'force-focus')}>
        <span className={cn('absolute top-px h-[20px] w-[20px] rounded-full bg-surface-card border border-border-strong', checked ? 'left-[10px]' : 'left-px')} />
      </button>
      {label}
    </label>
  )
}

export function Checkbox({ checked, indeterminate, label, state = 'default', swatch, onChange }:
  { checked: boolean; indeterminate?: boolean; label: ReactNode; state?: State; swatch?: string; onChange?: (v: boolean) => void }) {
  const disabled = state === 'disabled'
  const labelId = useId()
  return (
    <label className={cn('inline-flex items-center gap-2 text-body select-none', disabled ? 'opacity-50' : 'cursor-pointer')}>
      <button type="button" aria-labelledby={labelId} role="checkbox" aria-checked={indeterminate ? 'mixed' : checked} disabled={disabled} onClick={() => onChange?.(!checked)}
        className={cn('grid h-4 w-4 place-items-center rounded-[4px] border',
          checked || indeterminate ? 'bg-brand-700 border-brand-700 text-white' : 'bg-surface-card border-border-strong',
          state === 'hover' && !checked && 'border-neutral-500', state === 'focus' && 'force-focus')}>
        {indeterminate ? <Minus size={12} strokeWidth={2.5} /> : checked && <Check size={12} strokeWidth={2.5} />}
      </button>
      {swatch && <span aria-hidden className="h-3 w-3 rounded-[3px]" style={{ background: swatch }} />}
      <span id={labelId}>{label}</span>
    </label>
  )
}

/* ---------- Tabs (underline) ---------- */
export function Tabs({ tabs, value, onChange, children, forceHover }:
  { tabs: { value: string; label: string; count?: number }[]; value: string; onChange?: (v: string) => void; children?: ReactNode; forceHover?: string }) {
  if (!children) return <div role="group" aria-label="Filter results" className="flex flex-wrap gap-1 border-b border-border-default">
    {tabs.map(t => <button type="button" key={t.value} aria-pressed={t.value === value} onClick={() => onChange?.(t.value)}
      className={cn('inline-flex min-h-control items-center gap-2 border-b-2 px-3 text-secondary font-medium', t.value === value ? 'border-brand-700 text-brand-800' : 'border-transparent text-text-secondary hover:text-text-primary')}>
      {t.label}{t.count !== undefined && <span className="rounded-sm bg-surface-subtle px-2 text-caption tabular-nums">{t.count}</span>}
    </button>)}
  </div>
  return (
    <RTabs.Root value={value} onValueChange={onChange}>
      <RTabs.List className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <RTabs.Trigger key={t.value} value={t.value}
            className={cn('inline-flex h-control items-center gap-2 rounded-full border px-4 text-body font-medium',
              t.value === value ? 'border-transparent bg-cta text-text-onBrand shadow-card' : 'border-border-default bg-surface-card text-text-secondary hover:border-border-strong hover:text-text-primary',
              forceHover === t.value && 'text-text-primary border-border-strong')}>
            {t.label}
            {t.count !== undefined && (
              <span className={cn('rounded-full px-2 text-caption', t.value === value ? 'bg-surface-card text-brand-800' : 'bg-surface-subtle text-text-secondary')}>{t.count}</span>
            )}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
      {/* Tabs used as filters still need a panel per trigger, or aria-controls points at nothing (axe: critical). */}
      {children ?? tabs.map((t) => <RTabs.Content key={t.value} value={t.value} forceMount hidden={t.value !== value} className="sr-only">{t.label}</RTabs.Content>)}
    </RTabs.Root>
  )
}

/* ---------- Badges ---------- */
const STAGE_BG = ['bg-stage-0-tint', 'bg-stage-1-tint', 'bg-stage-2-tint', 'bg-stage-3-tint', 'bg-stage-4-tint']
const STAGE_TEXT = ['text-stage-0-text', 'text-stage-1-text', 'text-stage-2-text', 'text-stage-3-text', 'text-stage-4-text']
const STAGE_BORDER = ['border-stage-0-border', 'border-stage-1-border', 'border-stage-2-border', 'border-stage-3-border', 'border-stage-4-border']
export const STAGE_SOLID = ['bg-stage-0-solid', 'bg-stage-1-solid', 'bg-stage-2-solid', 'bg-stage-3-solid', 'bg-stage-4-solid']

export function StageBadge({ stage, label }: { stage: number; label: string }) {
  return (
    <span className={cn('inline-flex h-6 items-center gap-2 whitespace-nowrap rounded-full border px-3 text-caption font-medium', STAGE_BG[stage], STAGE_TEXT[stage], STAGE_BORDER[stage])}>
      <span aria-hidden className={cn('h-2 w-2 rounded-full', STAGE_SOLID[stage])} />
      Stage {stage} · {label}
    </span>
  )
}

const STATUS = {
  neutral: 'bg-neutral-100 text-text-secondary border-border-default', brand: 'bg-brand-50 text-brand-800 border-brand-100',
  info: 'bg-status-info-tint text-status-info-text border-status-info-border', warning: 'bg-status-warning-tint text-status-warning-text border-status-warning-border',
  orange: 'bg-status-orange-tint text-status-orange-text border-status-orange-border', slate: 'bg-status-slate-tint text-status-slate-text border-status-slate-border',
  danger: 'bg-status-danger-tint text-status-danger-text border-status-danger-border', success: 'bg-status-success-tint text-status-success-text border-status-success-border',
}
const DOT = { neutral: 'bg-neutral-500', brand: 'bg-brand-700', info: 'bg-status-info-icon', warning: 'bg-status-warning-icon', orange: 'bg-status-orange-icon',
  slate: 'bg-status-slate-icon', danger: 'bg-status-danger-icon', success: 'bg-status-success-icon' }
export type Tone = keyof typeof STATUS
export function Badge({ tone = 'neutral', dot, icon: Icon, children }: { tone?: Tone; pill?: boolean; dot?: boolean; icon?: LucideIcon; children: ReactNode }) {
  return (
    <span className={cn('inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full border px-3 text-caption font-medium', STATUS[tone])}>
      {dot && <span aria-hidden className={cn('mr-1 h-2 w-2 rounded-full', DOT[tone])} />}
      {Icon && <Icon size={12} strokeWidth={2} aria-hidden />}{children}
    </span>
  )
}

/** Line icon in a soft peach circle (landing page, stat cards, empty states). */
export function IconCircle({ icon: Icon, size = 'md' }: { icon: LucideIcon; size?: 'sm' | 'md' | 'lg' }) {
  const box = { sm: 'h-8 w-8', md: 'h-12 w-12', lg: 'h-16 w-16' }[size]
  return (
    <span aria-hidden className={cn('grid shrink-0 place-items-center rounded-full bg-accent-circle text-accent-icon', box)}>
      <Icon size={size === 'lg' ? 28 : size === 'md' ? 22 : 16} strokeWidth={1.75} />
    </span>
  )
}

export function ConfidenceBadge({ level }: { level: 'high' | 'moderate' | 'low' }) {
  const map = { high: ['slate', Info, 'High confidence'], moderate: ['info', Info, 'Moderate confidence'], low: ['warning', AlertTriangle, 'Low confidence'] } as const
  const [tone, icon, label] = map[level]
  return <Badge tone={tone} icon={icon}>{label}</Badge>
}

/* ---------- Tooltip & popover ---------- */
// One class string per overlay, shared by the live Radix component and the static panel shown in the gallery.
const TOOLTIP_CLS = 'z-50 max-w-[280px] rounded-control bg-neutral-900 px-2 py-1 text-caption text-white shadow-overlay'
const POPOVER_CLS = 'z-50 w-[280px] rounded-card border border-border-default bg-surface-card p-4 shadow-overlay'

export function TooltipPanel({ children }: { children: ReactNode }) {
  return <div role="tooltip" className={TOOLTIP_CLS}>{children}</div>
}
export function PopoverPanel({ children }: { children: ReactNode }) {
  return <div role="dialog" className={POPOVER_CLS}>{children}</div>
}

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RTooltip.Provider delayDuration={300}>
      <RTooltip.Root>
        <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
        <RTooltip.Portal>
          <RTooltip.Content sideOffset={8} className={cn('ds', TOOLTIP_CLS)}>{content}</RTooltip.Content>
        </RTooltip.Portal>
      </RTooltip.Root>
    </RTooltip.Provider>
  )
}

export function Popover({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <RPopover.Root>
      <RPopover.Trigger asChild>{trigger}</RPopover.Trigger>
      <RPopover.Portal>
        <RPopover.Content sideOffset={8} align="start" className={cn('ds', POPOVER_CLS)}>{children}</RPopover.Content>
      </RPopover.Portal>
    </RPopover.Root>
  )
}

/* ---------- Modal ---------- */
export function ModalPanel({ title, description, children, footer, onClose }:
  { title: string; description?: string; children?: ReactNode; footer?: ReactNode; onClose?: () => void }) {
  return (
    <div className="w-[480px] max-w-[calc(100vw-32px)] max-h-[85dvh] overflow-y-auto rounded-card bg-surface-card shadow-overlay">
      <div className="flex items-start justify-between gap-4 px-6 pt-6">
        <div>
          <h2 className="text-section font-semibold">{title}</h2>
          {description && <p className="mt-1 text-secondary text-text-secondary">{description}</p>}
        </div>
        <Button variant="ghost" compact aria-label="Close" onClick={onClose} className="px-2"><X {...ICON} /></Button>
      </div>
      <div className="px-6 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-border-default px-6 py-4">{footer}</div>}
    </div>
  )
}

export function Modal({ open, onOpenChange, ...panel }: Parameters<typeof ModalPanel>[0] & { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-40 bg-neutral-900/40" />
        <RDialog.Content aria-describedby={undefined} className="ds fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-transparent">
          <RDialog.Title className="sr-only">{panel.title}</RDialog.Title>
          <ModalPanel {...panel} onClose={() => onOpenChange(false)} />
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  )
}

/* ---------- Toast, alert ---------- */
const ALERT_ICON = { info: Info, warning: AlertTriangle, danger: CircleAlert, success: CircleCheck }
const ICON_TONE = { info: 'text-status-info-icon', warning: 'text-status-warning-icon', danger: 'text-status-danger-icon', success: 'text-status-success-icon' }
export function Toast({ tone = 'success', title, action }: { tone?: keyof typeof ALERT_ICON; title: string; action?: ReactNode }) {
  const Icon = ALERT_ICON[tone]
  return (
    <div role="status" className="flex w-[360px] max-w-[calc(100vw-32px)] items-center gap-3 rounded-card border border-border-default bg-surface-card px-4 py-3 shadow-overlay">
      <Icon size={16} strokeWidth={1.75} className={cn(ICON_TONE[tone], 'shrink-0')} aria-hidden />
      <span className="flex-1 text-body">{title}</span>
      {action}
    </div>
  )
}

export function Alert({ tone = 'info', title, children, action }: { tone?: keyof typeof ALERT_ICON; title: string; children?: ReactNode; action?: ReactNode }) {
  const Icon = ALERT_ICON[tone]
  const tones = { info: 'bg-status-info-tint border-status-info-border text-status-info-text', warning: 'bg-status-warning-tint border-status-warning-border text-status-warning-text',
    danger: 'bg-status-danger-tint border-status-danger-border text-status-danger-text', success: 'bg-status-success-tint border-status-success-border text-status-success-text' }
  return (
    <div role={tone === 'danger' ? 'alert' : 'note'} className={cn('flex gap-3 rounded-card border px-4 py-3', tones[tone])}>
      <Icon size={16} strokeWidth={1.75} className="mt-[2px] shrink-0" aria-hidden />
      <div className="flex-1">
        <p className="text-body font-medium">{title}</p>
        {children && <div className="mt-1 text-secondary">{children}</div>}
        {action && <div className="mt-2">{action}</div>}
      </div>
    </div>
  )
}

/* ---------- Card, key-value, empty, skeleton, progress, avatar ---------- */
export function Card({ title, subtitle, actions, footer, children, className }:
  { title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; footer?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <section className={cn('rounded-card border border-border-default bg-surface-card shadow-card', className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            {title && <h2 className="text-section font-semibold">{title}</h2>}
            {subtitle && <p className="mt-1 text-caption text-text-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
      {footer && <footer className="flex items-center justify-end gap-2 border-t border-border-default px-5 py-4">{footer}</footer>}
    </section>
  )
}

export function KeyValue({ items }: { items: { k: ReactNode; v: ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2 text-body">
      {items.map((it, i) => (
        <div key={i} className="contents">
          <dt className="text-text-secondary">{it.k}</dt>
          <dd className="text-right font-medium">{it.v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function EmptyState({ icon: Icon, title, body, action }: { icon: LucideIcon; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <IconCircle icon={Icon} />
      <h2 className="mt-4 text-section font-semibold">{title}</h2>
      <p className="mt-1 max-w-measure text-secondary text-text-secondary">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Skeleton({ className }: { className: string }) {
  return <span aria-hidden className={cn('block rounded-control bg-neutral-200', className)} />
}

export function Progress({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-caption text-text-secondary"><span>{label}</span><span>{Math.round(value)}%</span></div>
      <div role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100} aria-label={label} className="h-2 rounded-full bg-neutral-200">
        <div className="h-2 rounded-full bg-cta" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

export function Avatar({ name }: { name: string }) {
  const initials = name.split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  return <span title={name} className="grid h-8 w-8 place-items-center rounded-full bg-brand-50 text-caption font-semibold text-brand-800">{initials}</span>
}

/* ---------- Table ---------- */
export type Column<T> = { key: string; header: string; numeric?: boolean; width?: string; render: (row: T) => ReactNode }
export function Table<T>({ columns, rows, rowKey, selected, hovered, onRowClick, caption, maxHeight, selectable }:
  { columns: Column<T>[]; rows: T[]; rowKey: (r: T) => string; selected?: Set<string>; hovered?: string; onRowClick?: (r: T) => void;
    caption: string; maxHeight?: number; selectable?: boolean }) {
  return (
    <div className="overflow-auto rounded-card border border-border-default bg-surface-card shadow-card" style={{ maxHeight }} tabIndex={0} role="region" aria-label={caption}>
      <table className="w-full text-body">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 z-10 bg-surface-subtle">
          <tr className="border-b border-border-default">
            {selectable && <th scope="col" className="w-8 px-4"><span className="sr-only">Select</span></th>}
            {columns.map((c) => (
              <th key={c.key} scope="col" style={{ width: c.width }}
                className={cn('h-10 px-4 text-caption font-medium text-text-secondary', c.numeric ? 'text-right' : 'text-left')}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const k = rowKey(r), sel = selected?.has(k)
            return (
              <tr key={k} onClick={e => { if (!(e.target as HTMLElement).closest('a,button,input,select,textarea')) onRowClick?.(r) }} aria-selected={sel || undefined}
                className={cn('border-b border-border-default last:border-0', onRowClick && 'cursor-pointer',
                  sel ? 'bg-brand-50' : hovered === k ? 'bg-neutral-50' : 'hover:bg-brand-50')}>
                {selectable && <td className="px-4"><Checkbox checked={!!sel} label={<span className="sr-only">Select {k}</span>} /></td>}
                {columns.map((c) => (
                  <td key={c.key} className={cn('h-16 px-4 py-3 align-middle', c.numeric && 'text-right')}>{c.render(r)}</td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ---------- Breadcrumb, pagination ---------- */
export function Breadcrumb({ items }: { items: string[] }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-2 text-secondary text-text-secondary">
        {items.map((it, i) => (
          <li key={it} className="flex items-center gap-2">
            {i > 0 && <ChevronRight size={14} strokeWidth={1.75} aria-hidden className="text-text-muted" />}
            <span className={i === items.length - 1 ? 'font-medium text-text-primary' : ''} aria-current={i === items.length - 1 ? 'page' : undefined}>{it}</span>
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function Pagination({ page, pages, total, perPage, onPage }: { page: number; pages: number; total: number; perPage: number; onPage?: (p: number) => void }) {
  const from = (page - 1) * perPage + 1, to = Math.min(total, page * perPage)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-secondary text-text-secondary">
      <span>{from}–{to} of {total}</span>
      <div className="flex items-center gap-2">
        <Button variant="secondary" compact icon={ChevronLeft} state={page === 1 ? 'disabled' : 'default'} onClick={() => onPage?.(page - 1)}>Previous</Button>
        <span className="px-2">Page {page} of {pages}</span>
        <Button variant="secondary" compact state={page === pages ? 'disabled' : 'default'} onClick={() => onPage?.(page + 1)}>Next<ChevronRight {...ICON} aria-hidden /></Button>
      </div>
    </div>
  )
}
