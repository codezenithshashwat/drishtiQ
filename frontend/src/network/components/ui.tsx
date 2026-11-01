import { AlertTriangle, CheckCircle2, FlaskConical, Info, LoaderCircle, ShieldAlert, ShieldCheck, Volume2, VolumeX, X, type LucideIcon } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import { linkProps } from '../../app/router'
import type { CampState, Lang, Verification } from '../api'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'
import { cancelSpeech, speak, ttsSupported } from '../saathi/speech'

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')

type BtnProps = {
  variant?: 'primary' | 'secondary' | 'ghost' | 'saffron' | 'danger'; size?: 'md' | 'lg' | 'sm'; block?: boolean; to?: string
  icon?: LucideIcon; iconRight?: LucideIcon; busy?: boolean; children: ReactNode
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'>

export function Btn({ variant = 'primary', size = 'md', block, to, icon: I, iconRight: R, busy, children, className, ...rest }: BtnProps) {
  const cls = cx('nw-btn', variant, size !== 'md' && size, block && 'block', className)
  const inner = <>{busy ? <LoaderCircle size={20} className="nw-spin" aria-hidden /> : I && <I size={size === 'lg' ? 24 : 20} aria-hidden />}<span>{children}</span>{R && <R size={20} aria-hidden />}</>
  if (to) {
    const p = linkProps(to)
    return <a className={cls} href={p.href} onClick={(e) => { (rest.onClick as ((e: unknown) => void) | undefined)?.(e); p.onClick(e) }}>{inner}</a>
  }
  return <button className={cls} disabled={busy || rest.disabled} {...rest}>{inner}</button>
}

export function Notice({ tone = 'info', title, children, action }: { tone?: 'info' | 'warn' | 'danger' | 'success'; title?: string; children?: ReactNode; action?: ReactNode }) {
  const I = tone === 'success' ? CheckCircle2 : tone === 'info' ? Info : AlertTriangle
  return (
    <div className={cx('nw-notice', tone)} role={tone === 'danger' ? 'alert' : 'status'}>
      <I size={22} aria-hidden />
      <div style={{ flex: 1, minWidth: 0 }}>{title && <b>{title}</b>}{children}{action && <div style={{ marginTop: 10 }}>{action}</div>}</div>
    </div>
  )
}

export function Skeleton({ h = 120, className }: { h?: number; className?: string }) { return <div className={cx('nw-sk', className)} style={{ height: h }} aria-hidden /> }

export function Loading({ label }: { label?: string }) {
  const { t } = useI18n()
  return <div role="status" aria-live="polite" className="nw-grid c2"><span className="sr">{label ?? t('common.loading')}</span><Skeleton h={190} /><Skeleton h={190} /></div>
}

type TF = { label: string; hint?: string; error?: string | null; optional?: boolean } & InputHTMLAttributes<HTMLInputElement>
export function TextField({ label, hint, error, optional, className, ...rest }: TF) {
  const id = useId()
  const { t } = useI18n()
  const d = [hint && `${id}-h`, error && `${id}-e`].filter(Boolean).join(' ') || undefined
  return (
    <div className="nw-field">
      <label htmlFor={id}>{label}{optional && <span className="muted" style={{ fontWeight: 400 }}> · {t('common.optional')}</span>}</label>
      <input id={id} className={cx('nw-input', className)} aria-invalid={error ? true : undefined} aria-describedby={d} {...rest} />
      {hint && <span className="hint" id={`${id}-h`}>{hint}</span>}
      {error && <span className="err" id={`${id}-e`} role="alert"><AlertTriangle size={16} aria-hidden />{error}</span>}
    </div>
  )
}

export function PinField({ label, value, onChange, error, hint, autoFocus }: { label: string; value: string; onChange: (v: string) => void; error?: string | null; hint?: string; autoFocus?: boolean }) {
  return <TextField label={label} value={value} onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="postal-code" maxLength={6}
    className="pin" placeholder="• • • • • •" error={error} hint={hint} autoFocus={autoFocus} />
}

export function CheckRow({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return <label className="nw-check"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /><span>{children}</span></label>
}

export function Seg<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { v: T; label: string }[]; label: string }) {
  return (
    <div className="nw-field" role="group" aria-label={label}>
      <span className="lab">{label}</span>
      <div className="nw-seg">{options.map((o) => <button type="button" key={o.v} aria-pressed={value === o.v} onClick={() => onChange(o.v)}>{o.label}</button>)}</div>
    </div>
  )
}

/** Fades content up once when it scrolls into view. Content must never stay hidden, so it is also revealed when:
 * it is already on screen at load, anything inside it receives keyboard focus, the page is printed (and via print CSS),
 * IntersectionObserver is missing, and always under reduced motion (CSS). */
export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const [on, setOn] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') { setOn(true); return }
    const r = el.getBoundingClientRect()
    if (r.top < window.innerHeight && r.bottom > 0) { setOn(true); return }
    const show = () => { setOn(true); io.disconnect(); window.removeEventListener('beforeprint', show) }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) show() }, { rootMargin: '0px 0px -8% 0px' })
    io.observe(el)
    window.addEventListener('beforeprint', show)
    return () => { io.disconnect(); window.removeEventListener('beforeprint', show) }
  }, [])
  return <div ref={ref} className={cx('nw-reveal', on && 'in', className)} style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    onFocusCapture={() => setOn(true)}>{children}</div>
}

export function ReadAloud({ text, lang, label }: { text: string; lang: Lang; label?: string }) {
  const { t } = useI18n()
  const [on, setOn] = useState(false)
  const stop = useRef<(() => void) | null>(null)
  useEffect(() => () => { stop.current?.(); cancelSpeech() }, [])
  if (!ttsSupported()) return null
  return (
    <Btn variant="secondary" size="sm" icon={on ? VolumeX : Volume2} aria-pressed={on} type="button" onClick={() => {
      if (on) { stop.current?.(); setOn(false); return }
      setOn(true)
      stop.current = speak(text, lang, { onEnd: () => setOn(false) })
    }}>{on ? t('common.stopReading') : (label ?? t('common.readAloud'))}</Btn>
  )
}

export function VerificationBadge({ v }: { v: Verification }) {
  const { t } = useI18n()
  const I = v === 'verified' ? ShieldCheck : v === 'simulated' ? FlaskConical : ShieldAlert
  return <span className={cx('nw-badge', v)}><I size={15} aria-hidden />{t(`badge.${v}` as Key)}</span>
}

export function StateBadge({ s }: { s: CampState }) {
  const { t } = useI18n()
  return <span className={cx('nw-badge', s)}>{t(`state.${s}` as Key)}</span>
}

export function PageHead({ eyebrow, title, lead, back }: { eyebrow?: string; title: string; lead?: string; back?: ReactNode }) {
  return <header className="nw-page"><div className="wrap">{back}{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1 className="display" style={{ marginTop: 6 }}>{title}</h1>{lead && <p className="lead">{lead}</p>}</div></header>
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null)
  const id = useId()
  const { t } = useI18n()
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    const focusables = () => Array.from(box.current?.querySelectorAll<HTMLElement>('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])') ?? []).filter((e) => !e.hasAttribute('disabled'))
    focusables()[0]?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab') {
        const f = focusables(); if (!f.length) return
        const first = f[0], last = f[f.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); prev?.focus() }
  }, [onClose])
  return (
    <div className="nw-modal" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="box" role="dialog" aria-modal="true" aria-labelledby={id} ref={box}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' }}>
          <h2 id={id} className="display">{title}</h2>
          <button type="button" className="nw-btn ghost sm" onClick={onClose} aria-label={t('common.close')}><X size={22} aria-hidden /></button>
        </div>
        {children}
      </div>
    </div>
  )
}
