import { ArrowLeft, ChevronRight, History, Info, ListChecks, MessageSquareWarning, Search, Upload, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Avatar, Badge, cn } from '../design/components'
import { BrandLockup } from './BrandMark'
import { BRAND } from './brand'
import { linkProps, navigate, type Route } from './router'

type NavItem = { to: string; label: string; icon: LucideIcon; active: (r: Route) => boolean }
const NAV: NavItem[] = [
  { to: '/new', label: 'New screening', icon: Upload, active: (r) => r.name === 'new' },
  { to: '/worklist', label: 'Worklist', icon: ListChecks, active: (r) => (r.name === 'worklist' && r.tab !== 'reviewed') || r.name === 'case' || r.name === 'report' },
  { to: '/worklist?tab=reviewed', label: 'History', icon: History, active: (r) => r.name === 'worklist' && r.tab === 'reviewed' },
  { to: '/disagreements', label: 'Disagreements', icon: MessageSquareWarning, active: (r) => r.name === 'disagreements' },
  { to: '/about', label: 'About & settings', icon: Info, active: (r) => r.name === 'about' },
]

export type Crumb = { label: string; to?: string }

export function Shell({ route, crumbs, actions, version, children }:
  { route: Route; crumbs: Crumb[]; actions?: ReactNode; version?: string; children: ReactNode }) {
  const [q, setQ] = useState('')
  const back = crumbs.length > 1 ? crumbs[crumbs.length - 2] : null
  return (
    <div className="ds ds-glow flex min-h-screen text-text-primary">
      {/* Sidebar: 248 px from 1280 px up, a 64 px icon rail below. */}
      <aside className="sticky top-0 flex h-screen w-rail shrink-0 flex-col border-r border-border-default bg-surface-card/80 xl:w-sidebar">
        <a {...linkProps('/')} aria-label={`${BRAND}: home page`} className="flex h-20 items-center px-4 no-underline xl:px-5">
          <BrandLockup compact />
        </a>
        <nav aria-label="Main" className="flex flex-1 flex-col gap-1 px-3 py-4">
          {NAV.map((n) => {
            const active = n.active(route)
            return (
              <a key={n.to} {...linkProps(n.to)} aria-current={active ? 'page' : undefined} title={n.label}
                className={cn('flex h-11 items-center gap-3 rounded-control px-3 text-body font-medium no-underline',
                  active ? 'bg-brand-50 text-brand-800' : 'text-text-secondary hover:bg-brand-50 hover:text-text-primary')}>
                <n.icon size={19} strokeWidth={1.75} aria-hidden className={cn('shrink-0', active ? 'text-brand-700' : 'text-accent-icon')} />
                <span className="hidden xl:inline">{n.label}</span>
              </a>
            )
          })}
        </nav>
        <div className="hidden px-5 pb-6 xl:block">
          <p className="font-display text-[22px] leading-tight text-text-primary">AI for wider screening.</p>
          <p className="mt-2 text-caption text-text-muted">Research prototype, not a medical device. A clinician makes every decision.</p>
          <p className="mt-4 text-caption text-text-muted">Model</p>
          <p className="text-caption text-text-secondary break-words">{version ?? '—'}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-20 items-center justify-between gap-4 border-b border-border-default bg-surface-page/90 px-6">
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-3">
            {back?.to && (
              <a {...linkProps(back.to)} aria-label={`Back to ${back.label}`}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border-default bg-surface-card text-brand-700 no-underline hover:bg-brand-50">
                <ArrowLeft size={16} strokeWidth={2} aria-hidden />
              </a>
            )}
            <ol className="flex min-w-0 items-center gap-2 text-secondary text-text-secondary">
              {crumbs.map((c, i) => (
                <li key={i} className="flex min-w-0 items-center gap-2">
                  {i > 0 && <ChevronRight size={14} strokeWidth={1.75} aria-hidden className="text-text-muted" />}
                  {c.to && i < crumbs.length - 1
                    ? <a {...linkProps(c.to)} className="text-text-secondary no-underline hover:text-text-primary">{c.label}</a>
                    : <span className="truncate font-medium text-text-primary" aria-current={i === crumbs.length - 1 ? 'page' : undefined}>{c.label}</span>}
                </li>
              ))}
            </ol>
          </nav>
          <form role="search" className="relative hidden w-[320px] lg:block"
            onSubmit={(e) => { e.preventDefault(); navigate(`/worklist?tab=all&q=${encodeURIComponent(q.trim())}`) }}>
            <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
            <input aria-label="Search patients and cases" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search patient or case ID"
              className="h-control w-full rounded-full border border-border-default bg-surface-card pl-10 pr-4 text-body text-text-primary placeholder:text-text-muted hover:border-border-strong" />
          </form>
          <div className="flex shrink-0 items-center gap-3">
            {actions}
            <Badge tone="warning">Research prototype · not for clinical use</Badge>
            <span className="flex items-center gap-2">
              <Avatar name="Demo Clinician" />
              <span className="hidden text-secondary font-medium xl:inline">Demo clinician</span>
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-content flex-1 px-6 py-8">{children}</main>
      </div>
    </div>
  )
}

export function PageHeader({ title, subtitle, eyebrow, actions }: { title: string; subtitle?: ReactNode; eyebrow?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="font-display text-display-sm text-text-primary">{title}</h1>
        {subtitle && <p className="mt-2 max-w-measure text-body text-text-secondary">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
