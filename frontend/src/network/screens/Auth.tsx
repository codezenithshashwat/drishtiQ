import { ArrowLeft, ArrowRight, Eye, EyeOff, LogIn, UserPlus } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { flushSync } from 'react-dom'
import { linkProps, navigate } from '../../app/router'
import { net, type Lang, type User } from '../api'
import { Btn, CheckRow, Notice, PageHead, PinField, Seg, TextField } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import { useSession } from '../session'

export function PasswordField({ label, value, onChange, hint, error, autoComplete }: { label: string; value: string; onChange: (v: string) => void; hint?: string; error?: string | null; autoComplete: string }) {
  const { t } = useI18n()
  const [show, setShow] = useState(false)
  const id = useId()
  return (
    <div className="nw-field">
      <label htmlFor={id}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input id={id} className="nw-input" style={{ paddingRight: 64 }} type={show ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete}
          maxLength={128} aria-invalid={error ? true : undefined} />
        <button type="button" className="nw-btn ghost sm" onClick={() => setShow((s) => !s)} aria-pressed={show} aria-label={show ? t('auth.hide') : t('auth.show')}
          style={{ position: 'absolute', right: 6, top: 8, minWidth: 48, padding: 0 }}>{show ? <EyeOff size={22} aria-hidden /> : <Eye size={22} aria-hidden />}</button>
      </div>
      {hint && <span className="hint">{hint}</span>}
      {error && <span className="err" role="alert">{error}</span>}
    </div>
  )
}

const safeNext = (n: string | null) => (n && /^\/network(\/|$)/.test(n) ? n : null)
export const homeFor = (u: User) => (u.role === 'health_worker' ? '/network/worker' : u.role === 'organiser' || u.role === 'admin' ? '/network/organiser' : '/network/me')

export function LoginForm({ onDone, idLabel }: { onDone: (u: User) => void; idLabel?: string }) {
  const { t, errMsg } = useI18n()
  const { setUser } = useSession()
  const [ident, setIdent] = useState('')
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null)
    try { const r = await net.login(ident.trim(), pw); flushSync(() => setUser(r.user)); onDone(r.user) }  /* user is committed BEFORE navigating: a popstate render outranks a plain state update */ catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <form className="nw-card" style={{ display: 'grid', gap: 20 }} onSubmit={submit} noValidate>
      {err && <Notice tone="danger" title={t('auth.failed')}>{err}</Notice>}
      <TextField label={idLabel ?? t('auth.identifier')} value={ident} onChange={(e) => setIdent(e.target.value)} autoComplete="username" inputMode="email" autoFocus maxLength={120} hint={t('auth.identifierHint')} />
      <PasswordField label={t('auth.password')} value={pw} onChange={setPw} autoComplete="current-password" />
      <Btn type="submit" size="lg" icon={LogIn} busy={busy} disabled={!ident.trim() || !pw}>{t('nav.login')}</Btn>
    </form>
  )
}

export function Login({ next }: { next: string | null }) {
  const { t } = useI18n()
  return (
    <>
      <PageHead eyebrow={t('nav.me')} title={t('auth.loginTitle')} lead={t('auth.loginLead')} />
      <div className="wrap" style={{ maxWidth: 560, display: 'grid', gap: 20, paddingBottom: 56 }}>
        <LoginForm onDone={(u) => navigate(safeNext(next) ?? homeFor(u))} />
        <div className="nw-card tint" style={{ display: 'grid', gap: 12 }}>
          <b>{t('auth.noAccount')}</b>
          <p className="muted" style={{ fontSize: '.95rem' }}>{t('auth.optional')}</p>
          <Btn variant="secondary" to="/network/signup" icon={UserPlus}>{t('auth.signupTitle')}</Btn>
        </div>
        <p className="muted" style={{ fontSize: '.88rem' }}>{t('auth.forgot')} <a {...linkProps('/network/about')}>{t('foot.about')}</a></p>
      </div>
    </>
  )
}

export function Signup() {
  const { t, lang, errMsg } = useI18n()
  const { setUser } = useSession()
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [ident, setIdent] = useState('')
  const [pw, setPw] = useState('')
  const [village, setVillage] = useState('')
  const [pin, setPin] = useState('')
  const [lng, setLng] = useState<Lang>(lang)
  const [remind, setRemind] = useState(false)
  const [pref, setPref] = useState<'none' | 'sms' | 'call' | 'email'>('none')
  const [consent, setConsent] = useState(false)
  const [touched, setTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const isEmail = ident.includes('@')
  const identOk = isEmail ? /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(ident.trim()) : /^(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}$/.test(ident.trim())
  const e = {
    name: !name.trim() ? t('err.name_required') : null,
    ident: !identOk ? t('err.invalid_identifier') : null,
    pw: pw.length < 8 ? t('err.weak_password') : null,
    pin: pin && pin.length !== 6 ? t('err.invalid_pin') : null,
    consent: !consent ? t('err.consent_required') : null,
  }
  const next = () => { setTouched(true); if (e.name || e.ident || e.pw) return; setTouched(false); setStep(1); window.scrollTo({ top: 0 }) }
  const submit = async (ev: FormEvent) => {
    ev.preventDefault(); setTouched(true)
    if (e.pin || e.consent) return
    setBusy(true); setErr(null)
    try {
      const r = await net.signup({ name: name.trim(), identifier: ident.trim(), password: pw, village: village.trim() || undefined, pin: pin || undefined, language: lng, reminders_opt_in: remind, comm_pref: remind ? pref : 'none', consent: true })
      flushSync(() => setUser(r.user)); navigate('/network/me')
    } catch (x) { setErr(errMsg(x)); setStep(0) } finally { setBusy(false) }
  }
  return (
    <>
      <PageHead eyebrow={t('nav.me')} title={t('auth.signupTitle')} lead={t('auth.signupLead')} />
      <div className="wrap" style={{ maxWidth: 640, paddingBottom: 56 }}>
        <form className="nw-wiz" onSubmit={submit} noValidate>
          <div className="nw-prog" role="progressbar" aria-valuemin={1} aria-valuemax={2} aria-valuenow={step + 1} aria-label={t('wiz.progress', { n: step + 1, total: 2 })}>{[0, 1].map((i) => <i key={i} className={i <= step ? 'on' : ''} />)}</div>
          <Notice tone="info">{t('auth.optional')}</Notice>
          {err && <Notice tone="danger" title={t('auth.failed')}>{err}</Notice>}
          {step === 0 ? (
            <div className="nw-step-anim nw-card" style={{ display: 'grid', gap: 22 }}>
              <TextField label={t('wiz.name')} value={name} onChange={(x) => setName(x.target.value)} autoComplete="name" maxLength={80} autoFocus error={touched ? e.name : null} />
              <TextField label={t('auth.identifier')} value={ident} onChange={(x) => setIdent(x.target.value)} autoComplete="username" inputMode="email" maxLength={120} hint={t('auth.identHint')} error={touched ? e.ident : null} />
              <PasswordField label={t('auth.password')} value={pw} onChange={setPw} autoComplete="new-password" hint={t('auth.passwordHint')} error={touched ? e.pw : null} />
              <Notice tone="warn">{t('auth.unverified')}</Notice>
            </div>
          ) : (
            <div className="nw-step-anim nw-card" style={{ display: 'grid', gap: 22 }}>
              <PinField label={t('wiz.pin')} value={pin} onChange={setPin} error={touched ? e.pin : null} hint={t('common.optional')} />
              <TextField label={t('wiz.village')} value={village} onChange={(x) => setVillage(x.target.value)} optional maxLength={60} />
              <Seg value={lng} onChange={setLng} label={t('wiz.language')} options={[{ v: 'hi', label: 'हिंदी' }, { v: 'en', label: 'English' }]} />
              <CheckRow checked={remind} onChange={setRemind}>{t('auth.remind')}</CheckRow>
              {remind && <Seg value={pref} onChange={setPref} label={t('auth.pref')} options={[{ v: 'sms', label: 'SMS' }, { v: 'call', label: t('auth.call') }, { v: 'email', label: 'Email' }]} />}
              <CheckRow checked={consent} onChange={setConsent}>{t('auth.consent')}</CheckRow>
              {touched && e.consent && <p role="alert" style={{ color: 'var(--danger)', fontWeight: 500 }}>{e.consent}</p>}
              <p className="muted" style={{ fontSize: '.85rem' }}>{t('wiz.privacy')}</p>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            {step > 0 ? <Btn type="button" variant="secondary" icon={ArrowLeft} onClick={() => { setStep(0); setTouched(false) }}>{t('common.back')}</Btn> : <Btn variant="ghost" to="/network/login">{t('auth.haveAccount')}</Btn>}
            {step === 0 ? <Btn type="button" size="lg" iconRight={ArrowRight} onClick={next}>{t('common.next')}</Btn> : <Btn type="submit" size="lg" icon={UserPlus} busy={busy}>{t('auth.create')}</Btn>}
          </div>
        </form>
      </div>
    </>
  )
}
