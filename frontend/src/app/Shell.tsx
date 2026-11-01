import * as Dialog from '@radix-ui/react-dialog'
import { ArrowLeft, ChevronRight, History, Info, ListChecks, LogOut, Menu, MessageSquareWarning, Upload, UserRound, X, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Badge, Button, cn } from '../design/components'
import { BrandLockup } from './BrandMark'
import { BRAND } from './brand'
import type { Clinician } from './api'
import { linkProps, type Route } from './router'

type NavItem = { to: string; label: string; icon: LucideIcon; active: (r: Route) => boolean }
const NAV: NavItem[] = [
  { to: '/new', label: 'New screening', icon: Upload, active: r => r.name === 'new' },
  { to: '/worklist', label: 'Specialist Attention', icon: ListChecks, active: r => (r.name === 'worklist' && r.tab !== 'signed' && r.tab !== 'reviewed') || r.name === 'case' || r.name === 'report' },
  { to: '/worklist?tab=signed', label: 'Signed decisions', icon: History, active: r => r.name === 'worklist' && (r.tab === 'signed' || r.tab === 'reviewed') },
  { to: '/disagreements', label: 'Disagreements', icon: MessageSquareWarning, active: r => r.name === 'disagreements' },
  { to: '/about', label: 'Model & settings', icon: Info, active: r => r.name === 'about' },
]
export type Crumb = { label: string; to?: string }

function Navigation({ route, onNavigate, compact = false }: { route: Route; onNavigate?: () => void; compact?: boolean }) {
  return <nav aria-label="Main" className="flex flex-col gap-1 p-3">
    {NAV.map(n => {
      const link = linkProps(n.to)
      return <a key={n.to} {...link} onClick={e => { link.onClick(e); if (!e.metaKey && !e.ctrlKey && !e.shiftKey) onNavigate?.() }}
        aria-current={n.active(route) ? 'page' : undefined} aria-label={n.label} title={n.label}
        className={cn('flex min-h-control items-center gap-3 rounded-control px-3 py-2 text-secondary font-medium no-underline', n.active(route) ? 'bg-brand-50 text-brand-800' : 'text-text-secondary hover:bg-surface-subtle')}>
        <n.icon size={19} strokeWidth={1.75} aria-hidden className="shrink-0" />
        <span className={compact ? 'hidden xl:inline' : ''}>{n.label}</span>
      </a>
    })}
  </nav>
}

export function Shell({ route, crumbs, actions, version, clinician, onSignOut, children }: { route: Route; crumbs: Crumb[]; actions?: ReactNode; version?: string; clinician?: Clinician; onSignOut?: () => void; children: ReactNode }) {
  const [menu, setMenu] = useState(false)
  const back = crumbs.length > 1 ? crumbs[crumbs.length - 2] : null
  return <div className="ds workspace flex min-h-screen text-text-primary">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sticky top-0 hidden h-screen w-rail shrink-0 flex-col border-r border-border-default bg-surface-card md:flex xl:w-sidebar">
      <a {...linkProps('/specialists')} aria-label={`${BRAND}: specialist home`} className="flex h-topbar items-center px-4 no-underline xl:px-5"><BrandLockup compact /></a>
      <div className="flex-1 pt-4"><Navigation route={route} compact /></div>
      <div className="hidden border-t border-border-default p-5 xl:block">
        <p className="text-secondary font-medium">Human judgment. AI assistance.</p>
        <p className="mt-2 text-caption text-text-muted">Research prototype. Every clinical decision requires a clinician.</p>
        <a {...linkProps('/')} className="mt-3 inline-block text-caption text-text-secondary">Patient site: Saathi and eye camps</a>
        <details className="mt-4 text-caption text-text-muted"><summary className="cursor-pointer">System information</summary><p className="mt-2 break-words">{version ?? 'Model information unavailable'}</p></details>
      </div>
    </aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="sticky top-0 z-20 flex min-h-[64px] items-center justify-between gap-3 border-b border-border-default bg-surface-card px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Dialog.Root open={menu} onOpenChange={setMenu}>
            <Dialog.Trigger asChild><Button variant="ghost" aria-label="Open navigation" className="px-2 md:hidden"><Menu size={20} aria-hidden /></Button></Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-neutral-900/40" />
              <Dialog.Content aria-describedby={undefined} className="ds workspace fixed inset-y-0 left-0 z-50 w-[280px] max-w-[90vw] overflow-y-auto bg-surface-card p-3 shadow-overlay">
                <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                <div className="flex items-center justify-between p-3"><BrandLockup /><Dialog.Close asChild><Button variant="ghost" aria-label="Close navigation" className="px-2"><X size={20} /></Button></Dialog.Close></div>
                <Navigation route={route} onNavigate={() => setMenu(false)} />
                <p className="p-3 text-secondary text-text-secondary">Research prototype. Clinician review required.</p>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          {back?.to && <a {...linkProps(back.to)} aria-label={`Back to ${back.label}`} className="grid h-10 w-10 shrink-0 place-items-center rounded-control text-text-secondary hover:bg-surface-subtle"><ArrowLeft size={18} aria-hidden /></a>}
          <nav aria-label="Breadcrumb" className="min-w-0"><ol className="flex min-w-0 items-center gap-2 text-secondary">
            {crumbs.map((c, i) => <li key={i} className="flex min-w-0 items-center gap-2">
              {i > 0 && <ChevronRight size={14} aria-hidden className="shrink-0 text-text-muted" />}
              {c.to && i < crumbs.length - 1 ? <a {...linkProps(c.to)} className="truncate text-text-secondary no-underline">{c.label}</a> : <span className="truncate font-medium" aria-current="page">{c.label}</span>}
            </li>)}
          </ol></nav>
        </div>
        <div className="flex shrink-0 items-center gap-3">{actions}<span className="hidden sm:inline-flex"><Badge tone="slate">Research prototype</Badge></span>
          {clinician && <span className="flex items-center gap-2 border-l border-border-default pl-3">
            <span className="hidden max-w-[220px] items-center gap-2 truncate text-caption text-text-secondary lg:flex" title={`Signed in as ${clinician.name}`}><UserRound size={15} aria-hidden className="shrink-0" /><span className="truncate">{clinician.name}</span></span>
            <Button variant="ghost" compact icon={LogOut} onClick={onSignOut} aria-label={`Sign out ${clinician.name}`}>Sign out</Button>
          </span>}</div>
      </header>
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-content flex-1 px-4 py-6 sm:px-6 lg:py-8">{children}</main>
    </div>
  </div>
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; eyebrow?: string; actions?: ReactNode }) {
  return <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
    <div className="min-w-0"><h1 className="page-title">{title}</h1>{subtitle && <p className="mt-2 max-w-measure text-body text-text-secondary">{subtitle}</p>}</div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
}
