import { CheckCircle2, ClipboardList, Phone, UserPlus } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { navigate } from '../../../app/router'
import { net, type Camp, type Followup, type Lang, type RegResult, type Registration, type RegStatus } from '../../api'
import { Btn, CheckRow, Loading, Notice, PageHead, PinField, Seg, StateBadge, TextField } from '../../components/ui'
import { useI18n } from '../../i18n/I18n'
import type { Key } from '../../i18n/strings'
import { useSession } from '../../session'

const NEXT: Record<RegStatus, RegStatus[]> = {
  interest_received: ['contacted', 'confirmed_by_organiser', 'cancelled'], contacted: ['confirmed_by_organiser', 'no_show', 'cancelled'],
  confirmed_by_organiser: ['attended', 'no_show', 'cancelled'], attended: [], no_show: [], cancelled: [],
}
type Tab = 'requests' | 'followups' | 'assist'
const uuid = () => (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `k${Date.now()}${Math.random().toString(36).slice(2)}`)

export default function Worker() {
  const { t, campTitle } = useI18n()
  const { user, ready } = useSession()
  const [tab, setTab] = useState<Tab>('requests')
  const [camps, setCamps] = useState<Camp[]>([])
  useEffect(() => { if (ready && !user) navigate('/network/staff') }, [ready, user])
  useEffect(() => { if (user && (user.role === 'health_worker' || user.role === 'admin')) net.workerCamps().then((r) => setCamps(r.items), () => {}) }, [user])
  if (!ready || !user) return <div className="wrap" style={{ padding: 40 }}><Loading /></div>
  if (user.role !== 'health_worker' && user.role !== 'admin') return <div className="wrap" style={{ padding: 40 }}><Notice tone="warn">{t('err.forbidden')}</Notice></div>
  const tabs: { k: Tab; label: string }[] = [{ k: 'requests', label: t('worker.requests') }, { k: 'followups', label: t('worker.followups') }, { k: 'assist', label: t('worker.assist') }]
  return (
    <>
      <PageHead eyebrow={t('foot.staff')} title={t('worker.title')} lead={t('worker.lead', { n: camps.length })} />
      <div className="wrap" style={{ display: 'grid', gap: 22, paddingBottom: 64 }}>
        {user.is_prototype && <Notice tone="warn" title={t('staff.protoAcct')}>{t('staff.protoAcctBody')}</Notice>}
        <div className="nw-tabsline" role="tablist" aria-label={t('worker.title')}>
          {tabs.map((x) => <button key={x.k} type="button" role="tab" id={`tab-${x.k}`} aria-selected={tab === x.k} aria-controls={`panel-${x.k}`} onClick={() => setTab(x.k)}>{x.label}</button>)}
        </div>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === 'requests' && <Requests camps={camps} />}
          {tab === 'followups' && <Followups />}
          {tab === 'assist' && <Assist camps={camps.filter((c) => c.state === 'open')} campTitle={campTitle} />}
        </div>
      </div>
    </>
  )
}

function Requests({ camps }: { camps: Camp[] }) {
  const { t, errMsg, campTitle, when } = useI18n()
  const [camp, setCamp] = useState<number | null>(null)
  const [rows, setRows] = useState<Registration[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const load = useCallback(() => { net.workerRequests(camp).then((r) => setRows(r.items), (e) => setErr(errMsg(e))) }, [camp, errMsg])
  useEffect(() => { setRows(null); load() }, [load])
  const act = async (r: Registration, s: RegStatus) => { if (r.id === undefined) return; try { await net.setStatus(r.id, s); load() } catch (x) { setErr(errMsg(x)) } }
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="nw-field" style={{ maxWidth: 420 }}>
        <label htmlFor="wcamp">{t('worker.filter')}</label>
        <select id="wcamp" className="nw-input" value={camp ?? ''} onChange={(e) => setCamp(e.target.value ? Number(e.target.value) : null)}>
          <option value="">{t('worker.allCamps')}</option>{camps.map((c) => <option key={c.id} value={c.id}>{campTitle(c)}</option>)}
        </select>
      </div>
      {err && <Notice tone="danger">{err}</Notice>}
      {!rows && !err && <Loading />}
      {rows?.length === 0 && <div className="nw-empty"><ClipboardList size={40} aria-hidden /><p className="muted" style={{ marginTop: 8 }}>{t('worker.noRequests')}</p></div>}
      {rows?.map((r) => (
        <article key={r.ref} className="nw-row">
          <div>
            <b>{r.name}</b> <span className="nw-badge neutral">{t(`status.${r.status}` as Key)}</span>
            <p className="muted" style={{ fontSize: '.92rem' }}>{campTitle(r.camp)} · PIN {r.pin}{r.village ? ` · ${r.village}` : ''}</p>
            <p className="muted" style={{ fontSize: '.85rem' }}>{r.ref} · {when(r.created_at)} · {t(`channel.${r.channel}` as Key)}</p>
            {r.phone ? <p style={{ marginTop: 6 }}><a href={`tel:${r.phone}`} style={{ display: 'inline-flex', gap: 6, alignItems: 'center', minHeight: 44 }}><Phone size={16} aria-hidden />{r.phone}</a></p> : <p className="muted" style={{ fontSize: '.85rem', marginTop: 6 }}>{t('worker.noContact')}</p>}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {NEXT[r.status].map((s) => <Btn key={s} size="sm" variant={s === 'cancelled' || s === 'no_show' ? 'danger' : 'secondary'} onClick={() => void act(r, s)}>{t(`act.${s}` as Key)}</Btn>)}
          </div>
        </article>
      ))}
    </div>
  )
}

function Followups() {
  const { t, errMsg, campTitle, when } = useI18n()
  const [rows, setRows] = useState<Followup[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const load = useCallback(() => { net.workerFollowups().then((r) => setRows(r.items), (e) => setErr(errMsg(e))) }, [errMsg])
  useEffect(load, [load])
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      {err && <Notice tone="danger">{err}</Notice>}
      {!rows && !err && <Loading />}
      {rows?.length === 0 && <div className="nw-empty"><CheckCircle2 size={40} aria-hidden /><p className="muted" style={{ marginTop: 8 }}>{t('worker.noFollowups')}</p></div>}
      {rows?.map((f) => (
        <article key={f.id} className="nw-row">
          <div>
            <b>{t(`fu.${f.kind}` as Key)}: {f.name}</b>
            <p className="muted" style={{ fontSize: '.92rem' }}>{campTitle(f.camp)} · {f.ref}{f.due_at ? ` · ${t('worker.due')} ${when(f.due_at, false)}` : ''}</p>
            {f.phone && <a href={`tel:${f.phone}`} style={{ display: 'inline-flex', gap: 6, alignItems: 'center', minHeight: 44 }}><Phone size={16} aria-hidden />{f.phone}</a>}
          </div>
          <Btn size="sm" icon={CheckCircle2} onClick={async () => { try { await net.completeFollowup(f.id); load() } catch (x) { setErr(errMsg(x)) } }}>{t('worker.markDone')}</Btn>
        </article>
      ))}
    </div>
  )
}

function Assist({ camps, campTitle }: { camps: Camp[]; campTitle: (c: Camp) => string }) {
  const { t, errMsg } = useI18n()
  const [camp, setCamp] = useState<number | ''>('')
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [village, setVillage] = useState('')
  const [phone, setPhone] = useState('')
  const [lng, setLng] = useState<Lang>('hi')
  const [contactOk, setContactOk] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [res, setRes] = useState<RegResult | null>(null)
  const key = useRef(uuid())
  const ok = camp !== '' && name.trim() && /^\d{6}$/.test(pin) && agreed
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!ok) return
    setBusy(true); setErr(null)
    try { setRes(await net.assisted({ camp_id: Number(camp), name: name.trim(), pin, village: village.trim() || undefined, phone: phone.trim() || undefined, language: lng, consent: true, contact_consent: !!phone.trim() && contactOk, consent_spoken_confirmed: true, idempotency_key: key.current })) }
    catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  const again = () => { setRes(null); setName(''); setPin(''); setVillage(''); setPhone(''); setAgreed(false); setContactOk(false); key.current = uuid() }
  if (res) return (
    <div className="nw-card nw-success" style={{ maxWidth: 560 }}>
      <div className="tick"><CheckCircle2 size={48} aria-hidden /></div>
      <h2 className="display" style={{ fontSize: '1.7rem' }}>{res.duplicate ? t('done.already') : t('worker.recorded')}</h2>
      {res.receipt_code ? <><p className="muted">{t('worker.giveReceipt')}</p><div className="nw-receipt">{res.registration.ref}<br />{res.receipt_code}</div></> : <Notice tone="info">{t('done.dupNoCode')}</Notice>}
      <Notice tone="warn" title={t('wiz.notAppt')}>{t('done.notAppt')}</Notice>
      <Btn onClick={again} icon={UserPlus}>{t('worker.another')}</Btn>
    </div>
  )
  return (
    <form className="nw-card" style={{ display: 'grid', gap: 20, maxWidth: 620 }} onSubmit={submit} noValidate>
      <h2 className="display" style={{ fontSize: '1.5rem' }}>{t('worker.assist')}</h2>
      <p className="muted">{t('worker.assistLead')}</p>
      {err && <Notice tone="danger">{err}</Notice>}
      <div className="nw-field"><label htmlFor="acamp">{t('worker.camp')}</label>
        <select id="acamp" className="nw-input" value={camp} onChange={(e) => setCamp(e.target.value ? Number(e.target.value) : '')}><option value="">{t('worker.pickCamp')}</option>{camps.map((c) => <option key={c.id} value={c.id}>{campTitle(c)}</option>)}</select></div>
      <TextField label={t('wiz.name')} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
      <PinField label={t('wiz.pin')} value={pin} onChange={setPin} />
      <TextField label={t('wiz.village')} value={village} onChange={(e) => setVillage(e.target.value)} optional maxLength={60} />
      <TextField label={t('wiz.phone')} value={phone} onChange={(e) => setPhone(e.target.value)} optional inputMode="tel" maxLength={20} />
      {phone.trim() && <CheckRow checked={contactOk} onChange={setContactOk}>{t('wiz.contactOk')}</CheckRow>}
      <Seg value={lng} onChange={setLng} label={t('wiz.language')} options={[{ v: 'hi', label: 'हिंदी' }, { v: 'en', label: 'English' }]} />
      <CheckRow checked={agreed} onChange={setAgreed}>{t('worker.consent')}</CheckRow>
      <Btn type="submit" size="lg" busy={busy} disabled={!ok}>{t('worker.record')}</Btn>
      <span className="sr"><StateBadge s="open" /></span>
    </form>
  )
}
