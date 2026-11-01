import { useEffect, useState, type FormEvent } from 'react'
import { navigate } from '../../../app/router'
import { net, type CampForm } from '../../api'
import { Btn, Loading, Notice, PageHead, PinField, Seg, TextField } from '../../components/ui'
import { useI18n } from '../../i18n/I18n'
import { useSession } from '../../session'
import { BackLink } from '../Camps'

const blank = (): CampForm => {
  const d = new Date(Date.now() + 7 * 864e5); d.setMinutes(0, 0, 0)
  const f = (h: number) => { const x = new Date(d); x.setHours(h); return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}T${String(h).padStart(2, '0')}:00` }
  return { title_en: '', title_hi: '', place_label: '', village: '', district: '', state: 'Madhya Pradesh', pin: '', starts_at: f(10), ends_at: f(16), capacity: null, price_info: '', contact_public: '', publish_state: 'draft' }
}

export default function CampEditor({ id }: { id: number | 'new' }) {
  const { t, errMsg } = useI18n()
  const { user, ready } = useSession()
  const [f, setF] = useState<CampForm | null>(id === 'new' ? blank() : null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState(false)
  useEffect(() => { if (ready && !user) navigate('/network/staff') }, [ready, user])
  useEffect(() => {
    if (id === 'new' || !user) return
    net.orgCamps().then((r) => {
      const c = r.items.find((x) => x.id === id)
      if (!c) { setErr(t('err.camp_not_found')); return }
      setDemo(c.is_demo)
      setF({ title_en: c.title.en, title_hi: c.title.hi, place_label: c.place.label, village: c.place.village ?? '', district: c.place.district, state: c.place.state, pin: c.place.pin,
        starts_at: c.starts_at.slice(0, 16), ends_at: c.ends_at.slice(0, 16), capacity: c.planned_capacity, price_info: c.price_info ?? '', contact_public: c.contact_public ?? '', publish_state: c.publish_state })
    }, (e) => setErr(errMsg(e)))
  }, [id, user, errMsg, t])
  const back = <BackLink to="/network/organiser" label={t('org.title')} />
  if (!ready || !user) return <div className="wrap" style={{ padding: 40 }}><Loading /></div>
  if (user.role !== 'organiser' && user.role !== 'admin') return <div className="wrap" style={{ padding: 40 }}><Notice tone="warn">{t('err.forbidden')}</Notice></div>
  if (!f) return <div className="wrap" style={{ padding: '32px 20px' }}>{back}{err ? <Notice tone="danger">{err}</Notice> : <Loading />}</div>
  const set = <K extends keyof CampForm>(k: K, v: CampForm[K]) => setF((x) => (x ? { ...x, [k]: v } : x))
  const ok = f.title_en.trim() && f.place_label.trim() && f.district.trim() && f.state.trim() && /^\d{6}$/.test(f.pin) && f.starts_at && f.ends_at
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!ok) return
    setBusy(true); setErr(null)
    try { await net.saveCamp(id, { ...f, village: f.village || null, price_info: f.price_info || null, contact_public: f.contact_public || null }); navigate('/network/organiser') }
    catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <>
      <PageHead back={back} eyebrow={t('org.title')} title={id === 'new' ? t('org.new') : t('org.editTitle')} />
      <div className="wrap" style={{ maxWidth: 720, paddingBottom: 64 }}>
        <form className="nw-card" style={{ display: 'grid', gap: 20 }} onSubmit={submit} noValidate>
          {demo && <Notice tone="info">{t('org.demoCampNote')}</Notice>}
          <Notice tone="warn">{t('org.verifyNote')}</Notice>
          {err && <Notice tone="danger">{err}</Notice>}
          <TextField label={t('org.titleEn')} value={f.title_en} onChange={(e) => set('title_en', e.target.value)} maxLength={120} />
          <TextField label={t('org.titleHi')} value={f.title_hi} onChange={(e) => set('title_hi', e.target.value)} maxLength={120} optional lang="hi" />
          <TextField label={t('org.place')} value={f.place_label} onChange={(e) => set('place_label', e.target.value)} maxLength={120} />
          <TextField label={t('wiz.village')} value={f.village ?? ''} onChange={(e) => set('village', e.target.value)} maxLength={60} optional />
          <TextField label={t('org.district')} value={f.district} onChange={(e) => set('district', e.target.value)} maxLength={60} />
          <TextField label={t('org.state')} value={f.state} onChange={(e) => set('state', e.target.value)} maxLength={60} />
          <PinField label={t('wiz.pin')} value={f.pin} onChange={(v) => set('pin', v)} />
          <TextField label={t('org.starts')} type="datetime-local" value={f.starts_at} onChange={(e) => set('starts_at', e.target.value)} />
          <TextField label={t('org.ends')} type="datetime-local" value={f.ends_at} onChange={(e) => set('ends_at', e.target.value)} />
          <TextField label={t('org.capacity')} type="number" min={0} max={100000} value={f.capacity ?? ''} onChange={(e) => set('capacity', e.target.value === '' ? null : Number(e.target.value))} optional hint={t('camp.capacityNote')} />
          <TextField label={t('camp.price')} value={f.price_info ?? ''} onChange={(e) => set('price_info', e.target.value)} maxLength={120} optional />
          <TextField label={t('camp.contact')} value={f.contact_public ?? ''} onChange={(e) => set('contact_public', e.target.value)} maxLength={120} optional />
          <Seg value={f.publish_state} onChange={(v) => set('publish_state', v)} label={t('org.publish')} options={[{ v: 'draft', label: t('org.draft') }, { v: 'published', label: t('org.published') }, { v: 'closed', label: t('state.closed') }, { v: 'cancelled', label: t('state.cancelled') }]} />
          <Btn type="submit" size="lg" busy={busy} disabled={!ok}>{t('common.save')}</Btn>
        </form>
      </div>
    </>
  )
}
