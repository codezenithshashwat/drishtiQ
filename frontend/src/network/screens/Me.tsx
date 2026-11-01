import { BookOpenText, Download, LogOut, Mic, Pencil, Search, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { linkProps, navigate } from '../../app/router'
import { net, type Lang, type Registration, type RegStatus } from '../api'
import { Btn, CheckRow, Loading, Modal, Notice, PageHead, PinField, Seg, TextField } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'
import { useSession } from '../session'
import { ScreeningStatus, StatusTimeline } from './Register'

const FINAL: RegStatus[] = ['attended', 'no_show', 'cancelled']

export function Me() {
  const { t, lang, setLang, errMsg, when, campTitle } = useI18n()
  const { user, ready, setUser, logout } = useSession()
  const [regs, setRegs] = useState<Registration[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const [name, setName] = useState('')
  const [village, setVillage] = useState('')
  const [pin, setPin] = useState('')
  const [lng, setLng] = useState<Lang>('hi')
  const [remind, setRemind] = useState(false)
  const [pref, setPref] = useState<'none' | 'sms' | 'call' | 'email'>('none')
  const [open, setOpen] = useState<string | null>(null)
  const [del, setDel] = useState(false)
  const [claimRef, setClaimRef] = useState('')
  const [claimCode, setClaimCode] = useState('')

  useEffect(() => { if (ready && !user) navigate('/network/login?next=/network/me') }, [ready, user])
  useEffect(() => { if (user && user.role !== 'user') navigate(user.role === 'health_worker' ? '/network/worker' : '/network/organiser') }, [user])
  const userId = user?.id
  const userRole = user?.role
  const load = useCallback(() => { net.myRegs().then((r) => setRegs(r.items), (e) => setErr(errMsg(e))) }, [errMsg])
  useEffect(() => { if (userId && userRole === 'user') load() }, [userId, userRole, load])
  useEffect(() => { // a receipt kept from a guest registration is attached right after sign-up
    if (!userId || userRole !== 'user') return
    let r: { ref: string; code: string } | null = null
    try { r = JSON.parse(sessionStorage.getItem('dqn.receipt') ?? 'null'); sessionStorage.removeItem('dqn.receipt') } catch { /* ignore */ }
    if (r) net.claim(r.ref, r.code).then(() => load(), () => { /* already owned or invalid: leave it */ })
  }, [userId, userRole, load])
  useEffect(() => { if (user) { setName(user.name); setVillage(user.village ?? ''); setPin(user.pin ?? ''); setLng(user.language); setRemind(user.reminders_opt_in); setPref(user.comm_pref) } }, [user, editing])

  if (!ready || !user || user.role !== 'user') return <div className="wrap" style={{ padding: '40px 20px' }}><Loading /></div>

  const save = async () => {
    setErr(null)
    try {
      const r = await net.updateMe({ name, village, pin, language: lng, reminders_opt_in: remind, comm_pref: remind ? pref : 'none' })
      setUser(r.user); setLang(r.user.language); setEditing(false); setSaved(true)
    } catch (x) { setErr(errMsg(x)) }
  }
  const exportData = async () => {
    try {
      const d = await net.exportMe()
      const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' }))
      const a = document.createElement('a'); a.href = url; a.download = 'my-drishtiq-data.json'; a.click(); URL.revokeObjectURL(url)
    } catch (x) { setErr(errMsg(x)) }
  }
  const cancel = async (r: Registration) => { if (r.id === undefined) return; try { await net.cancel(r.id); load() } catch (x) { setErr(errMsg(x)) } }
  const claim = async () => { setErr(null); try { await net.claim(claimRef.trim(), claimCode.trim()); setClaimRef(''); setClaimCode(''); load() } catch (x) { setErr(errMsg(x)) } }

  return (
    <>
      <PageHead eyebrow="My DrishtiQ" title={t('me.hello', { name: user.name.split(' ')[0] })} lead={t('me.lead')} />
      <div className="wrap" style={{ display: 'grid', gap: 24, paddingBottom: 64 }}>
        {err && <Notice tone="danger" title={t('common.errorTitle')}>{err}</Notice>}
        {saved && <Notice tone="success">{t('me.saved')}</Notice>}

        <div className="nw-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))', alignItems: 'start' }}>
          <section className="nw-card" style={{ display: 'grid', gap: 18 }} aria-labelledby="prof-t">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
              <h2 id="prof-t" className="display" style={{ fontSize: '1.5rem' }}>{t('me.profile')}</h2>
              {!editing && <Btn variant="secondary" size="sm" icon={Pencil} onClick={() => { setEditing(true); setSaved(false) }}>{t('me.edit')}</Btn>}
            </div>
            {editing ? (
              <div style={{ display: 'grid', gap: 18 }}>
                <TextField label={t('wiz.name')} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
                <PinField label={t('wiz.pin')} value={pin} onChange={setPin} />
                <TextField label={t('wiz.village')} value={village} onChange={(e) => setVillage(e.target.value)} maxLength={60} />
                <Seg value={lng} onChange={setLng} label={t('wiz.language')} options={[{ v: 'hi', label: 'हिंदी' }, { v: 'en', label: 'English' }]} />
                <CheckRow checked={remind} onChange={setRemind}>{t('auth.remind')}</CheckRow>
                {remind && <Seg value={pref} onChange={setPref} label={t('auth.pref')} options={[{ v: 'sms', label: 'SMS' }, { v: 'call', label: t('auth.call') }, { v: 'email', label: 'Email' }]} />}
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}><Btn onClick={() => void save()}>{t('common.save')}</Btn><Btn variant="ghost" onClick={() => setEditing(false)}>{t('common.cancel')}</Btn></div>
              </div>
            ) : (
              <dl className="nw-review">
                <div><dt>{t('wiz.name')}</dt><dd>{user.name}</dd></div>
                <div><dt>{user.identifier_type === 'email' ? 'Email' : t('wiz.phone')}</dt><dd>{user.identifier_masked} <span className="nw-badge unverified">{t('me.notVerified')}</span></dd></div>
                <div><dt>{t('wiz.village')}</dt><dd>{user.village || '—'}</dd></div>
                <div><dt>{t('wiz.pin')}</dt><dd>{user.pin || '—'}</dd></div>
                <div><dt>{t('wiz.language')}</dt><dd>{user.language === 'hi' ? 'हिंदी' : 'English'}</dd></div>
                <div><dt>{t('me.reminders')}</dt><dd>{user.reminders_opt_in ? t('me.on') : t('me.off')}</dd></div>
              </dl>
            )}
          </section>

          <section className="nw-card" style={{ display: 'grid', gap: 16 }} aria-labelledby="reg-t">
            <h2 id="reg-t" className="display" style={{ fontSize: '1.5rem' }}>{t('me.regs')}</h2>
            {!regs && !err && <Loading />}
            {regs && regs.length === 0 && (
              <div className="nw-empty" style={{ padding: 28 }}><p className="muted" style={{ marginBottom: 16 }}>{t('me.noRegs')}</p><Btn icon={Search} to="/network/camps">{t('home.ctaCamps')}</Btn></div>
            )}
            {regs?.map((r) => (
              <div key={r.ref} className="nw-row" style={{ gridTemplateColumns: '1fr' }}>
                <div>
                  <b>{campTitle(r.camp)}</b>
                  <p className="muted" style={{ fontSize: '.92rem' }}>{when(r.camp.starts_at)} · {r.ref}</p>
                  <p style={{ marginTop: 6 }}><span className="nw-badge neutral">{t(`status.${r.status}` as Key)}</span></p>
                </div>
                {open === r.ref && <StatusTimeline status={r.status} />}
                {open === r.ref && r.screening && r.screening.state !== 'not_linked' && <ScreeningStatus s={r.screening} />}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Btn variant="secondary" size="sm" aria-expanded={open === r.ref} onClick={() => setOpen(open === r.ref ? null : r.ref)}>{t('me.progress')}</Btn>
                  <Btn variant="ghost" size="sm" to={`/network/camps/${r.camp.id}`}>{t('camps.details')}</Btn>
                  {!FINAL.includes(r.status) && <Btn variant="danger" size="sm" onClick={() => void cancel(r)}>{t('me.cancelInterest')}</Btn>}
                </div>
              </div>
            ))}
            <details>
              <summary style={{ cursor: 'pointer', fontWeight: 600, minHeight: 44, display: 'flex', alignItems: 'center' }}>{t('me.addReceipt')}</summary>
              <div style={{ display: 'grid', gap: 14, marginTop: 12 }}>
                <p className="muted" style={{ fontSize: '.9rem' }}>{t('me.addReceiptBody')}</p>
                <TextField label={t('status.ref')} value={claimRef} onChange={(e) => setClaimRef(e.target.value.toUpperCase())} maxLength={20} />
                <TextField label={t('status.code')} value={claimCode} onChange={(e) => setClaimCode(e.target.value.toUpperCase())} maxLength={20} />
                <Btn variant="secondary" disabled={!claimRef || !claimCode} onClick={() => void claim()}>{t('me.add')}</Btn>
              </div>
            </details>
          </section>
        </div>

        <section className="nw-card tint" style={{ display: 'grid', gap: 14 }}>
          <h2 className="display" style={{ fontSize: '1.4rem' }}>{t('me.readTitle')}</h2>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Btn variant="secondary" icon={BookOpenText} to="/network/learn/why-screening">{t('me.read1')}</Btn>
            <Btn variant="secondary" icon={BookOpenText} to="/network/learn/what-happens">{t('me.read2')}</Btn>
            <Btn variant="secondary" icon={Mic} to="/network/saathi">{t('home.ctaTalk')}</Btn>
          </div>
        </section>

        <section className="nw-card" style={{ display: 'grid', gap: 14 }} aria-labelledby="priv-t">
          <h2 id="priv-t" className="display" style={{ fontSize: '1.3rem' }}>{t('me.privacy')}</h2>
          <p className="muted" style={{ fontSize: '.95rem' }}>{t('me.privacyBody')} <a {...linkProps('/network/about')}>{t('foot.about')}</a></p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Btn variant="secondary" size="sm" icon={Download} onClick={() => void exportData()}>{t('me.export')}</Btn>
            <Btn variant="danger" size="sm" icon={Trash2} onClick={() => setDel(true)}>{t('me.delete')}</Btn>
            <Btn variant="ghost" size="sm" icon={LogOut} onClick={() => { void logout().then(() => navigate('/')) }}>{t('nav.logout')}</Btn>
          </div>
        </section>
      </div>

      {del && (
        <Modal title={t('me.deleteTitle')} onClose={() => setDel(false)}>
          <p>{t('me.deleteBody')}</p>
          <div style={{ display: 'grid', gap: 10 }}>
            <Btn variant="danger" size="lg" onClick={async () => { try { await net.deleteMe(); setUser(null); navigate('/') } catch (x) { setErr(errMsg(x)); setDel(false) } }}>{t('me.deleteYes')}</Btn>
            <Btn variant="secondary" onClick={() => setDel(false)}>{t('common.cancel')}</Btn>
          </div>
        </Modal>
      )}
      <span className="sr" lang={lang} />
    </>
  )
}
