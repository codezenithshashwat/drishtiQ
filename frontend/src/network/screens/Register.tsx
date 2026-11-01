import { ArrowLeft, ArrowRight, Check, Clock, Copy, Search, ShieldCheck, UserPlus, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { navigate } from '../../app/router'
import { useUnsavedChanges } from '../../app/useUnsavedChanges'
import { net, NetError, type Camp, type Lang, type RegResult, type Registration, type RegStatus, type Screening } from '../api'
import { Btn, CheckRow, cx, Loading, Notice, PageHead, PinField, Seg, TextField, VerificationBadge } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'
import { useSession } from '../session'
import { BackLink } from './Camps'

const PHONE = /^(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}$/
const uuid = () => (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `k${Date.now()}${Math.random().toString(36).slice(2)}`)

export function Register({ id, pin: pin0, viaSaathi }: { id: number; pin: string | null; viaSaathi: boolean }) {
  const { t, lang, errMsg, campTitle, when } = useI18n()
  const { user } = useSession()
  const [camp, setCamp] = useState<Camp | null>(null)
  const [loadErr, setLoadErr] = useState<string | null>(null)
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [lng, setLng] = useState<Lang>(lang)
  const [pin, setPin] = useState(pin0 && /^\d{6}$/.test(pin0) ? pin0 : '')
  const [village, setVillage] = useState('')
  const [phone, setPhone] = useState('')
  const [contactOk, setContactOk] = useState(false)
  const [consent, setConsent] = useState(false)
  const [touched, setTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<RegResult | null>(null)
  const key = useRef(uuid())
  const seeded = useRef(false)

  useEffect(() => { let live = true; net.camp(id).then((c) => live && setCamp(c), (e) => live && setLoadErr(errMsg(e))); return () => { live = false } }, [id, errMsg])
  useEffect(() => { // signed-in people start with their saved profile
    if (!user || seeded.current) return
    seeded.current = true
    setName((n) => n || user.name); setVillage((v) => v || user.village || ''); setPin((p) => p || user.pin || ''); setLng(user.language)
  }, [user])

  const dirty = !result && (name !== '' || phone !== '' || village !== '' || consent)
  useUnsavedChanges(dirty, t('wiz.leave'))

  const e1 = !name.trim() ? t('err.name_required') : null
  const e2 = !/^\d{6}$/.test(pin) ? t('err.invalid_pin') : phone.trim() && !PHONE.test(phone.trim()) ? t('err.invalid_phone') : null
  const e3 = !consent ? t('err.consent_required') : null
  const errs = [e1, e2, e3]
  const hasPhone = phone.trim().length > 0

  const next = () => { setTouched(true); if (errs[step]) return; setTouched(false); setStep((s) => s + 1); window.scrollTo({ top: 0 }) }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (errs[2] || errs[1] || errs[0]) return
    setBusy(true); setErr(null)
    try {
      setResult(await net.register({ camp_id: id, name: name.trim(), pin, village: village.trim() || undefined, phone: phone.trim() || undefined, language: lng, consent: true,
        contact_consent: hasPhone && contactOk, idempotency_key: key.current, via_saathi: viaSaathi }))
    } catch (x) { setErr(errMsg(x)); if (x instanceof NetError && x.code === 'invalid_pin') setStep(1) } finally { setBusy(false) }
  }

  const back = <BackLink to={camp ? `/network/camps/${camp.id}` : '/network/camps'} label={t('wiz.backCamp')} />
  if (loadErr) return <div className="wrap" style={{ padding: '32px 20px' }}>{back}<Notice tone="danger" title={t('common.errorTitle')}>{loadErr}</Notice></div>
  if (!camp) return <div className="wrap" style={{ padding: '32px 20px' }}><Loading /></div>
  if (camp.state !== 'open' && !result) return <div className="wrap" style={{ padding: '32px 20px', display: 'grid', gap: 16 }}>{back}<Notice tone="warn" title={t('wiz.notOpen')}>{t(`camp.reason.${camp.state}` as Key)}</Notice><Btn to="/network/camps">{t('camps.title')}</Btn></div>
  if (result) return <Done result={result} camp={camp} loggedIn={!!user} />

  const steps = [t('wiz.s1'), t('wiz.s2'), t('wiz.s3')]
  return (
    <>
      <PageHead back={back} eyebrow={t('wiz.eyebrow')} title={t('wiz.title')} />
      <div className="wrap" style={{ paddingBottom: 56 }}>
        <form className="nw-wiz" onSubmit={submit} noValidate>
          <div className="nw-card tint" style={{ padding: 18 }}>
            <p style={{ fontWeight: 600 }}>{campTitle(camp)}</p>
            <p className="muted" style={{ fontSize: '.92rem', margin: '2px 0 8px' }}>{when(camp.starts_at)}</p>
            <VerificationBadge v={camp.verification} />
          </div>
          <div>
            <div className="nw-prog" role="progressbar" aria-valuemin={1} aria-valuemax={3} aria-valuenow={step + 1} aria-label={t('wiz.progress', { n: step + 1, total: 3 })}>{[0, 1, 2].map((i) => <i key={i} className={i <= step ? 'on' : ''} />)}</div>
            <p className="eyebrow" style={{ marginTop: 10 }}>{t('wiz.progress', { n: step + 1, total: 3 })} · {steps[step]}</p>
          </div>
          {err && <Notice tone="danger" title={t('wiz.failed')}>{err}</Notice>}

          {step === 0 && (
            <div className="nw-step-anim nw-card" style={{ display: 'grid', gap: 22 }}>
              <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('wiz.q1')}</h2>
              <TextField label={t('wiz.name')} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} autoFocus hint={t('wiz.nameHint')} error={touched ? e1 : null} />
              <Seg value={lng} onChange={setLng} label={t('wiz.language')} options={[{ v: 'hi', label: 'हिंदी' }, { v: 'en', label: 'English' }]} />
            </div>
          )}
          {step === 1 && (
            <div className="nw-step-anim nw-card" style={{ display: 'grid', gap: 22 }}>
              <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('wiz.q2')}</h2>
              <PinField label={t('wiz.pin')} value={pin} onChange={setPin} error={touched && !/^\d{6}$/.test(pin) ? t('err.invalid_pin') : null} />
              <TextField label={t('wiz.village')} value={village} onChange={(e) => setVillage(e.target.value)} optional maxLength={60} autoComplete="address-level2" />
              <TextField label={t('wiz.phone')} value={phone} onChange={(e) => setPhone(e.target.value)} optional inputMode="tel" autoComplete="tel" maxLength={20} hint={t('wiz.phoneHint')} error={touched && phone.trim() && !PHONE.test(phone.trim()) ? t('err.invalid_phone') : null} />
              {hasPhone && <CheckRow checked={contactOk} onChange={setContactOk}>{t('wiz.contactOk')}</CheckRow>}
            </div>
          )}
          {step === 2 && (
            <div className="nw-step-anim nw-card" style={{ display: 'grid', gap: 20 }}>
              <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('wiz.q3')}</h2>
              <dl className="nw-review">
                <div><dt>{t('wiz.name')}</dt><dd>{name}</dd></div>
                <div><dt>{t('wiz.pin')}</dt><dd>{pin}</dd></div>
                {village && <div><dt>{t('wiz.village')}</dt><dd>{village}</dd></div>}
                {hasPhone && <div><dt>{t('wiz.phone')}</dt><dd>{phone}</dd></div>}
                <div><dt>{t('wiz.language')}</dt><dd>{lng === 'hi' ? 'हिंदी' : 'English'}</dd></div>
              </dl>
              <Notice tone="info" title={t('wiz.notAppt')}>{t('wiz.notApptBody')}</Notice>
              <CheckRow checked={consent} onChange={setConsent}>{t('wiz.consent')}</CheckRow>
              {touched && e3 && <p className="err" style={{ color: 'var(--danger)', fontWeight: 500 }} role="alert">{e3}</p>}
              <p className="muted" style={{ fontSize: '.85rem' }}>{t('wiz.privacy')}</p>
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, justifyContent: 'space-between' }}>
            {step > 0 ? <Btn type="button" variant="secondary" icon={ArrowLeft} onClick={() => { setStep((s) => s - 1); setTouched(false) }}>{t('common.back')}</Btn> : <span />}
            {step < 2
              ? <Btn type="button" size="lg" iconRight={ArrowRight} onClick={next}>{t('common.next')}</Btn>
              : <Btn type="submit" size="lg" icon={Check} busy={busy}>{t('wiz.confirm')}</Btn>}
          </div>
        </form>
      </div>
    </>
  )
}

function Done({ result, camp, loggedIn }: { result: RegResult; camp: Camp; loggedIn: boolean }) {
  const { t, campTitle, when } = useI18n()
  const [copied, setCopied] = useState(false)
  const r = result.registration
  const code = result.receipt_code
  const copy = async () => { try { await navigator.clipboard.writeText(`${r.ref} ${code}`); setCopied(true) } catch { /* clipboard blocked */ } }
  useEffect(() => { document.getElementById('nw-done')?.focus() }, [])
  return (
    <div className="wrap" style={{ padding: '40px 20px 64px' }}>
      <div className="nw-wiz nw-success">
        <div className="tick"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12.5l4.5 4.5L19 7.5" /></svg></div>
        <h1 id="nw-done" tabIndex={-1} className="display" style={{ fontSize: 'clamp(1.9rem,4.4vw,2.7rem)', outline: 'none' }}>{result.duplicate ? t('done.already') : t('done.title')}</h1>
        <p className="lead muted" style={{ maxWidth: '44ch' }}>{t('done.status')}: <b style={{ color: 'var(--ink)' }}>{t(`status.${r.status}` as Key)}</b></p>
        <div className="nw-card" style={{ width: '100%', display: 'grid', gap: 6, textAlign: 'left' }}>
          <b>{campTitle(camp)}</b><span className="muted">{when(camp.starts_at)}</span>
        </div>
        {code ? (
          <div style={{ display: 'grid', gap: 10, justifyItems: 'center', width: '100%' }}>
            <p style={{ fontWeight: 600 }}>{t('done.receipt')}</p>
            <div className="nw-receipt" aria-label={`${r.ref} ${code}`}>{r.ref}<br />{code}</div>
            <Btn variant="secondary" size="sm" icon={copied ? Check : Copy} onClick={copy}>{copied ? t('common.copied') : t('common.copy')}</Btn>
            <p className="muted" style={{ fontSize: '.92rem' }}>{t('done.keep')}</p>
          </div>
        ) : <Notice tone="info">{t('done.dupNoCode')}</Notice>}
        <Notice tone="warn" title={t('wiz.notAppt')}>{t('done.notAppt')}</Notice>
        <div style={{ display: 'grid', gap: 12, width: '100%' }}>
          {code && <Btn size="lg" block icon={Search} to={`/network/status?ref=${r.ref}&code=${code}`}>{t('done.check')}</Btn>}
          {loggedIn ? <Btn variant="secondary" block to="/network/me">{t('done.myDq')}</Btn> : <Btn variant="secondary" block icon={UserPlus} to="/network/signup" onClick={() => { if (code) try { sessionStorage.setItem('dqn.receipt', JSON.stringify({ ref: r.ref, code })) } catch { /* ignore */ } }}>{t('done.save')}</Btn>}
          <Btn variant="ghost" block to="/network/camps">{t('done.more')}</Btn>
        </div>
      </div>
    </div>
  )
}

const FLOW: RegStatus[] = ['interest_received', 'contacted', 'confirmed_by_organiser', 'attended']

export function StatusTimeline({ status }: { status: RegStatus }) {
  const { t } = useI18n()
  if (status === 'cancelled' || status === 'no_show') {
    return <p className="nw-notice warn" role="status"><XCircle size={22} aria-hidden /><span><b>{t(`status.${status}` as Key)}</b></span></p>
  }
  const at = FLOW.indexOf(status)
  return (
    <ol className="nw-time" aria-label={t('status.timeline')}>
      {FLOW.map((s, i) => (
        <li key={s} className={i < at ? 'done' : i === at ? 'now' : 'off'} aria-current={i === at ? 'step' : undefined}>
          <span className="dot">{i < at ? <Check size={18} aria-hidden /> : i === at ? <Clock size={18} aria-hidden /> : <span aria-hidden>{i + 1}</span>}</span>
          <span><b>{t(`status.${s}` as Key)}</b><br /><span className="muted" style={{ fontSize: '.88rem' }}>{t(`status.${s}.d` as Key)}</span></span>
        </li>
      ))}
    </ol>
  )
}

/** What the patient may know about their screening: process steps, then the next step their eye-care team signed. */
export function ScreeningStatus({ s }: { s: Screening }) {
  const { t, when } = useI18n()
  const eyes = (list: ('right' | 'left')[] | undefined) => (list ?? []).map((e) => t(`scr.eye.${e}` as Key)).join(t('scr.and'))
  const decided = s.state === 'decision_recorded' && s.next_action
  const urgent = s.next_action === 'urgent_referral' || s.next_action === 'referral' || s.next_action === 'examination'
  return (
    <section className={cx('nw-card nw-screening', decided && (urgent ? 'urgent' : 'decided'))} aria-labelledby="scr-t" style={{ display: 'grid', gap: 10 }}>
      <p className="eyebrow" id="scr-t">{t('scr.title')}</p>
      <h3 className="display" style={{ fontSize: '1.35rem' }}>{t(`scr.${s.state}` as Key)}</h3>
      {decided ? <p style={{ fontSize: '1.08rem', fontWeight: 600 }}>{t(`next.${s.next_action}` as Key)}</p>
        : s.state !== 'decision_recorded' && <p className="muted">{s.state === 'incomplete' ? t('scr.incomplete.d', { eyes: eyes(s.missing_eyes) }) : t(`scr.${s.state}.d` as Key)}</p>}
      {s.state !== 'incomplete' && (s.missing_eyes?.length ?? 0) > 0 && <p className="muted">{t('scr.alsoIncomplete', { eyes: eyes(s.missing_eyes) })}</p>}
      {decided && (s.eyes_awaiting_review ?? 0) > 0 && <p className="muted">{t('scr.alsoPending')}</p>}
      {s.state === 'incomplete' && s.quality_provisional && <p className="muted">{t('scr.quality_check.d')}</p>}
      {decided && s.decided_at && <p className="muted" style={{ fontSize: '.88rem' }}>{t('scr.decided', { d: when(s.decided_at) })}</p>}
      <p className="muted" style={{ fontSize: '.85rem' }}>{t('scr.notResult')}</p>
    </section>
  )
}

export function Status({ ref0, code0 }: { ref0: string | null; code0: string | null }) {
  const { t, errMsg, campTitle, when } = useI18n()
  const { user } = useSession()
  const [ref, setRef] = useState(ref0 ?? '')
  const [code, setCode] = useState(code0 ?? '')
  const [res, setRes] = useState<Registration | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [claimed, setClaimed] = useState(false)
  const run = useMemo(() => async (r: string, c: string) => {
    setBusy(true); setErr(null); setRes(null)
    try { setRes(await net.lookup(r.trim(), c.trim())) } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }, [errMsg])
  useEffect(() => { if (ref0 && code0) void run(ref0, code0) }, [ref0, code0, run])

  return (
    <>
      <PageHead eyebrow={t('nav.me')} title={t('status.title')} lead={t('status.lead')} />
      <div className="wrap" style={{ paddingBottom: 56, display: 'grid', gap: 22, maxWidth: 760 }}>
        <form className="nw-card" style={{ display: 'grid', gap: 18 }} onSubmit={(e) => { e.preventDefault(); void run(ref, code) }}>
          <TextField label={t('status.ref')} value={ref} onChange={(e) => setRef(e.target.value.toUpperCase())} placeholder="DQN-XXXXXX" autoCapitalize="characters" maxLength={20} />
          <TextField label={t('status.code')} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="XXXX-XXXX" autoCapitalize="characters" maxLength={20} />
          <Btn type="submit" size="lg" icon={Search} busy={busy} disabled={!ref.trim() || !code.trim()}>{t('status.find')}</Btn>
        </form>
        {err && <Notice tone="danger" title={t('common.errorTitle')}>{err}</Notice>}
        {busy && <Loading />}
        {res && (
          <section className="nw-card" style={{ display: 'grid', gap: 18 }} aria-live="polite">
            <div><p className="eyebrow">{res.ref}</p><h2 className="display" style={{ fontSize: '1.6rem' }}>{campTitle(res.camp)}</h2><p className="muted">{when(res.camp.starts_at)} · {res.camp.place.district}</p></div>
            <StatusTimeline status={res.status} />
            {res.screening && <ScreeningStatus s={res.screening} />}
            <p className="muted" style={{ fontSize: '.88rem' }}>{t('status.updated', { d: when(res.updated_at) })} · {t('wiz.notAppt')}</p>
            {user && user.role === 'user' && !claimed && (
              <Btn variant="secondary" icon={ShieldCheck} onClick={async () => { try { await net.claim(res.ref, code.trim()); setClaimed(true) } catch (x) { setErr(errMsg(x)) } }}>{t('status.claim')}</Btn>
            )}
            {claimed && <Notice tone="success">{t('status.claimed')}</Notice>}
          </section>
        )}
        <Btn variant="ghost" onClick={() => navigate('/network/camps')}>{t('done.more')}</Btn>
      </div>
    </>
  )
}
