import { CalendarPlus, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { navigate } from '../../../app/router'
import { net, type Camp, type OrgSummary } from '../../api'
import { Btn, Loading, Notice, PageHead, StateBadge, VerificationBadge } from '../../components/ui'
import { useI18n } from '../../i18n/I18n'
import type { Key } from '../../i18n/strings'
import { useSession } from '../../session'

export default function Organiser() {
  const { t, errMsg, campTitle, when } = useI18n()
  const { user, ready } = useSession()
  const [sum, setSum] = useState<OrgSummary | null>(null)
  const [camps, setCamps] = useState<Camp[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (ready && !user) navigate('/network/staff') }, [ready, user])
  const ok = !!user && (user.role === 'organiser' || user.role === 'admin')
  const load = useCallback(() => {
    net.orgSummary().then(setSum, (e) => setErr(errMsg(e)))
    net.orgCamps().then((r) => setCamps(r.items), (e) => setErr(errMsg(e)))
  }, [errMsg])
  useEffect(() => { if (ok) load() }, [ok, load])
  if (!ready || !user) return <div className="wrap" style={{ padding: 40 }}><Loading /></div>
  if (!ok) return <div className="wrap" style={{ padding: 40 }}><Notice tone="warn">{t('err.forbidden')}</Notice></div>
  const max = Math.max(1, ...(sum?.interest_by_pin.map((x) => x.n) ?? [1]))
  const verify = async (c: Camp) => { try { await net.verifyCamp(c.id, c.verification === 'verified' ? 'unverified' : 'verified'); load() } catch (x) { setErr(errMsg(x)) } }

  return (
    <>
      <PageHead eyebrow={t('foot.staff')} title={t('org.title')} lead={t('org.lead')} />
      <div className="wrap" style={{ display: 'grid', gap: 24, paddingBottom: 64 }}>
        {user.is_prototype && <Notice tone="warn" title={t('staff.protoAcct')}>{t('staff.protoAcctBody')}</Notice>}
        {sum?.is_demo_data && <Notice tone="info" title={t('org.demoTitle')}>{t('org.demoBody')}</Notice>}
        {err && <Notice tone="danger">{err}</Notice>}
        {!sum && !err && <Loading />}
        {sum && (
          <>
            <div className="nw-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))' }}>
              <div className="nw-stat"><b>{sum.camps}</b><span>{t('org.statCamps')}</span></div>
              <div className="nw-stat"><b>{sum.open_camps}</b><span>{t('org.statOpen')}</span></div>
              <div className="nw-stat"><b>{sum.interest_total}</b><span>{t('org.statInterest')}</span></div>
              <div className="nw-stat"><b>{sum.planned_capacity_open}</b><span>{t('org.statCapacity')}</span></div>
            </div>
            <div className="nw-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))' }}>
              <section className="nw-card" style={{ display: 'grid', gap: 14 }} aria-labelledby="pin-t">
                <h2 id="pin-t" style={{ fontSize: '1.15rem' }}>{t('org.byPin')}</h2>
                {sum.interest_by_pin.length === 0 ? <p className="muted">{t('org.noInterest')}</p> : (
                  <ul style={{ display: 'grid', gap: 10 }}>{sum.interest_by_pin.map((x) => (
                    <li key={x.pin} className="nw-bar"><span>{x.pin}</span><span style={{ background: 'var(--bg2)', borderRadius: 99, display: 'block' }}><i style={{ width: `${(x.n / max) * 100}%` }} /></span><b>{x.n}</b></li>
                  ))}</ul>
                )}
              </section>
              <section className="nw-card" style={{ display: 'grid', gap: 10 }} aria-labelledby="st-t">
                <h2 id="st-t" style={{ fontSize: '1.15rem' }}>{t('org.byStatus')}</h2>
                <dl className="nw-review">{(Object.entries(sum.status_totals) as [keyof typeof sum.status_totals, number][]).map(([k, v]) => <div key={k}><dt>{t(`status.${k}` as Key)}</dt><dd>{v}</dd></div>)}</dl>
              </section>
            </div>
          </>
        )}
        <section style={{ display: 'grid', gap: 14 }} aria-labelledby="camps-t">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <h2 id="camps-t" className="display" style={{ fontSize: '1.6rem' }}>{t('org.camps')}</h2>
            <Btn icon={CalendarPlus} to="/network/organiser/camps/new">{t('org.new')}</Btn>
          </div>
          {!camps && !err && <Loading />}
          {camps?.map((c) => (
            <article key={c.id} className="nw-row">
              <div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}><VerificationBadge v={c.verification} /><StateBadge s={c.state} />{c.publish_state === 'draft' && <span className="nw-badge neutral">{t('org.draft')}</span>}</div>
                <b>{campTitle(c)}</b>
                <p className="muted" style={{ fontSize: '.92rem' }}>{when(c.starts_at)} · PIN {c.place.pin} · {c.place.district}</p>
                <p style={{ fontSize: '.92rem', marginTop: 4 }}>{t('org.interest', { n: c.interest_total ?? 0 })}{c.planned_capacity ? ` / ${c.planned_capacity}` : ''}</p>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <Btn variant="secondary" size="sm" to={`/network/organiser/camps/${c.id}`}>{t('me.edit')}</Btn>
                {user.role === 'admin' && !c.is_demo && <Btn variant="secondary" size="sm" icon={ShieldCheck} onClick={() => void verify(c)}>{c.verification === 'verified' ? t('org.unverify') : t('org.verify')}</Btn>}
              </div>
            </article>
          ))}
        </section>
      </div>
    </>
  )
}
