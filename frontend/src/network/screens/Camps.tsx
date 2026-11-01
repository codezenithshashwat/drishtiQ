import { Building2, CalendarDays, ChevronLeft, Coins, Mic, Phone, SearchX, Search, Users, MapPin } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { navigate, linkProps } from '../../app/router'
import { net, type Camp, type CampSearch } from '../api'
import { CampCard } from '../components/CampCard'
import { Btn, CheckRow, Loading, Notice, PageHead, PinField, ReadAloud, StateBadge, TextField, VerificationBadge } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'

export function BackLink({ to, label }: { to: string; label: string }) {
  return <a className="nw-crumb" {...linkProps(to)}><ChevronLeft size={20} aria-hidden />{label}</a>
}

export function CampFinder({ pin, q }: { pin: string | null; q: string | null }) {
  const { t, errMsg } = useI18n()
  const [pinIn, setPin] = useState(pin ?? '')
  const [qIn, setQ] = useState(q ?? '')
  const [past, setPast] = useState(false)
  const [data, setData] = useState<CampSearch | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [fieldErr, setFieldErr] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const validPin = !pin || /^\d{6}$/.test(pin)

  useEffect(() => {
    if (!validPin) return
    let live = true
    setData(null); setErr(null)
    net.camps({ pin, q, include_expired: past }).then((d) => live && setData(d), (e) => live && setErr(errMsg(e)))
    return () => { live = false }
  }, [pin, q, past, tick, validPin, errMsg])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (pinIn && !/^\d{6}$/.test(pinIn)) { setFieldErr(t('err.invalid_pin')); return }
    setFieldErr(null)
    const p = new URLSearchParams(); if (pinIn) p.set('pin', pinIn); if (qIn.trim()) p.set('q', qIn.trim())
    navigate(`/network/camps${p.toString() ? `?${p}` : ''}`)
  }
  const items = data?.items ?? []
  const allDemo = items.length > 0 && items.every((c) => c.is_demo)

  return (
    <>
      <PageHead eyebrow={t('nav.camps')} title={t('camps.title')} lead={t('camps.lead')} />
      <div className="wrap" style={{ display: 'grid', gap: 24, paddingBottom: 40 }}>
        <form className="nw-search" onSubmit={submit} noValidate>
          <PinField label={t('camps.pinLabel')} value={pinIn} onChange={setPin} error={fieldErr} hint={t('camps.pinHint')} />
          <TextField label={t('camps.placeLabel')} value={qIn} onChange={(e) => setQ(e.target.value)} optional placeholder={t('camps.placePh')} maxLength={40} />
          <Btn type="submit" size="lg" icon={Search}>{t('camps.search')}</Btn>
        </form>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          <Btn variant="secondary" size="sm" icon={Mic} to="/network/saathi">{t('camps.askSaathi')}</Btn>
          <div style={{ maxWidth: 360 }}><CheckRow checked={past} onChange={setPast}>{t('camps.showPast')}</CheckRow></div>
        </div>

        {!validPin && <Notice tone="warn">{t('err.invalid_pin')}</Notice>}
        {err && <Notice tone="danger" title={t('common.errorTitle')} action={<Btn size="sm" variant="secondary" onClick={() => setTick((n) => n + 1)}>{t('common.retry')}</Btn>}>{err}</Notice>}
        {validPin && !data && !err && <Loading />}
        {data && (
          <section aria-live="polite" aria-label={t('camps.results')} style={{ display: 'grid', gap: 18 }}>
            {items.length > 0 && <p style={{ fontWeight: 600 }}>{t('camps.found', { n: items.length })}{pin && data.exact === 0 ? ` · ${t('camps.onlyNearby')}` : ''}</p>}
            {allDemo && <Notice tone="info" title={t('camps.demoTitle')}>{t('camps.demoBody')}</Notice>}
            {items.length === 0 ? (
              <div className="nw-empty">
                <div className="ico"><SearchX size={40} aria-hidden /></div>
                <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('camps.emptyTitle')}</h2>
                <p className="muted" style={{ maxWidth: '52ch', margin: '10px auto 24px' }}>{t('camps.emptyBody')}</p>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                  <Btn to="/network/saathi" icon={Mic}>{t('camps.askSaathi')}</Btn>
                  <Btn variant="secondary" to="/network/learn">{t('camps.learnMore')}</Btn>
                </div>
              </div>
            ) : <div className="nw-grid c2">{items.map((c) => <CampCard key={c.id} camp={c} />)}</div>}
          </section>
        )}
      </div>
    </>
  )
}

function reasonKey(c: Camp): Key | null {
  return c.state === 'open' ? null : (`camp.reason.${c.state}` as Key)
}

export function CampDetail({ id }: { id: number }) {
  const { t, lang, when, campTitle, errMsg } = useI18n()
  const [camp, setCamp] = useState<Camp | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { let live = true; net.camp(id).then((c) => live && setCamp(c), (e) => live && setErr(errMsg(e))); return () => { live = false } }, [id, errMsg])

  const back = <BackLink to="/network/camps" label={t('camps.backToList')} />
  if (err) return <div className="wrap" style={{ padding: '32px 20px' }}>{back}<Notice tone="danger" title={t('common.errorTitle')}>{err}</Notice></div>
  if (!camp) return <div className="wrap" style={{ padding: '32px 20px' }}>{back}<Loading /></div>
  const p = camp.place
  const verified = camp.verification === 'verified'
  const spoken = `${campTitle(camp)}. ${when(camp.starts_at)}. ${[p.village || p.label, p.district].join(', ')}, PIN ${p.pin}. ${camp.organiser.name}. ${camp.is_demo ? t('camp.demoSpoken') : ''}`
  const reason = reasonKey(camp)

  return (
    <div className="wrap" style={{ padding: '24px 20px 56px' }}>
      {back}
      <div className="nw-detail">
        <article className="nw-card" style={{ display: 'grid', gap: 22 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><VerificationBadge v={camp.verification} /><StateBadge s={camp.state} /></div>
          <h1 className="display" style={{ fontSize: 'clamp(1.7rem,3.6vw,2.5rem)' }}>{campTitle(camp)}</h1>
          {camp.is_demo && <Notice tone="info" title={t('camps.demoTitle')}>{t('camps.demoBody')}</Notice>}
          {camp.verification === 'unverified' && <Notice tone="warn">{t('camp.unverifiedNote')}</Notice>}
          <dl className="nw-kv">
            <div><dt><CalendarDays size={22} aria-hidden />{t('camp.when')}</dt><dd>{when(camp.starts_at)} – {new Intl.DateTimeFormat(lang === 'hi' ? 'hi-IN' : 'en-IN', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' }).format(new Date(camp.ends_at))}</dd></div>
            <div><dt><MapPin size={22} aria-hidden />{t('camp.where')}</dt><dd>{[p.label, p.district, p.state].filter(Boolean).join(', ')} · PIN {p.pin}</dd></div>
            <div><dt><Building2 size={22} aria-hidden />{t('camp.organiser')}</dt><dd>{camp.organiser.name} <VerificationBadge v={camp.organiser.verification} /></dd></div>
            <div><dt><Users size={22} aria-hidden />{t('camp.capacity')}</dt><dd>{camp.planned_capacity ? t('camp.capacityVal', { n: camp.planned_capacity }) : t('camp.notProvided')}</dd></div>
            <div><dt><Coins size={22} aria-hidden />{t('camp.price')}</dt><dd>{verified && camp.price ? camp.price : t('camp.notProvided')}</dd></div>
            <div><dt><Phone size={22} aria-hidden />{t('camp.contact')}</dt><dd>{verified && camp.contact ? camp.contact : t('camp.notProvided')}</dd></div>
          </dl>
          <p className="muted" style={{ fontSize: '.9rem' }}>{t('camp.capacityNote')}</p>
          <div><ReadAloud text={spoken} lang={lang} /></div>
        </article>
        <aside className="nw-aside nw-card" style={{ display: 'grid', gap: 16 }}>
          <h2 className="display" style={{ fontSize: '1.5rem' }}>{t('camp.interestTitle')}</h2>
          <p className="muted">{t('camp.interestBody')}</p>
          {reason ? <Notice tone="warn">{t(reason)}</Notice> : <Btn size="lg" block to={`/network/camps/${camp.id}/register`}>{t('camps.register')}</Btn>}
          <Btn variant="secondary" block icon={Mic} to="/network/saathi">{t('camp.askSaathi')}</Btn>
        </aside>
      </div>
    </div>
  )
}
