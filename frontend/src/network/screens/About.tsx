import { Check, FlaskConical, Hourglass } from 'lucide-react'
import { Btn, Notice, PageHead } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'

const ROWS: { k: Key; s: 'on' | 'demo' | 'plan' }[] = [
  { k: 'about.r1', s: 'on' }, { k: 'about.r2', s: 'on' }, { k: 'about.r3', s: 'on' }, { k: 'about.r4', s: 'on' }, { k: 'about.r5', s: 'on' },
  { k: 'about.r6', s: 'demo' }, { k: 'about.r7', s: 'demo' }, { k: 'about.r8', s: 'plan' }, { k: 'about.r9', s: 'on' }, { k: 'about.r10', s: 'plan' },
]

export function About() {
  const { t } = useI18n()
  const label = { on: t('about.implemented'), demo: t('about.simulated'), plan: t('about.planned') }
  const Icon = { on: Check, demo: FlaskConical, plan: Hourglass }
  return (
    <>
      <PageHead eyebrow={t('foot.about')} title={t('about.title')} lead={t('about.lead')} />
      <div className="wrap" style={{ display: 'grid', gap: 28, paddingBottom: 64, maxWidth: 900 }}>
        <Notice tone="warn" title={t('about.protoTitle')}>{t('about.protoBody')}</Notice>
        <section className="nw-card" style={{ display: 'grid', gap: 14 }}>
          <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('about.statusTitle')}</h2>
          <ul style={{ display: 'grid', gap: 10 }}>
            {ROWS.map((r) => { const I = Icon[r.s]; return (
              <li key={r.k} className="nw-row" style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center', padding: '12px 16px' }}>
                <span className={`nw-badge ${r.s === 'on' ? 'verified' : r.s === 'demo' ? 'simulated' : 'neutral'}`}><I size={15} aria-hidden />{label[r.s]}</span>
                <span>{t(r.k)}</span>
              </li>
            ) })}
          </ul>
        </section>
        <section className="nw-card" style={{ display: 'grid', gap: 12 }}>
          <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('about.connectTitle')}</h2>
          <p>{t('about.connectBody')}</p>
          <ol className="nw-steps" style={{ marginTop: 8 }}>
            <li><div><b>{t('home.flow1')}</b><span>{t('home.flow1d')}</span></div></li>
            <li><div><b>{t('home.flow2')}</b><span>{t('home.flow2d')}</span></div></li>
            <li><div><b>{t('home.flow3')}</b><span>{t('home.flow3d')}</span></div></li>
            <li><div><b>{t('home.flow4')}</b><span>{t('home.flow4d')}</span></div></li>
          </ol>
          <Notice tone="info">{t('about.separate')}</Notice>
        </section>
        <section className="nw-card" style={{ display: 'grid', gap: 12 }}>
          <h2 className="display" style={{ fontSize: '1.6rem' }}>{t('about.privTitle')}</h2>
          <ul style={{ display: 'grid', gap: 8, paddingLeft: 0 }}>{(['about.p1', 'about.p2', 'about.p3', 'about.p4', 'about.p5'] as Key[]).map((k) => <li key={k}>• {t(k)}</li>)}</ul>
        </section>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}><Btn to="/">{t('nav.home')}</Btn><Btn variant="secondary" to="/specialists">{t('foot.ai')}</Btn></div>
      </div>
    </>
  )
}
