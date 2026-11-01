import { ArrowRight, BookOpenText, ClipboardCheck, Info, Mic, Search, Stethoscope, Ticket } from 'lucide-react'
import { linkProps } from '../../app/router'
import camp from '../../assets/landing/screening_camp.webp'
import { HeroSun } from '../components/art'
import { SaathiOrb } from '../components/SaathiOrb'
import { Btn, Reveal } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'
import { useSaathi } from '../saathi/SaathiProvider'

const SERVICES: { to: string; icon: typeof Search; k: Key; d: Key; tint: string; ink: string }[] = [
  { to: '/network/camps', icon: Search, k: 'home.svcCamps', d: 'home.svcCampsD', tint: '#E3F3EC', ink: '#1F5F50' },
  { to: '/network/learn', icon: BookOpenText, k: 'home.svcLearn', d: 'home.svcLearnD', tint: '#FFF1DC', ink: '#7A4000' },
  { to: '/network/camps', icon: ClipboardCheck, k: 'home.svcRegister', d: 'home.svcRegisterD', tint: '#E6EEFB', ink: '#1C3068' },
  // Staff tools stay available from the footer; the home page is for patients and families.
  { to: '/network/status', icon: Ticket, k: 'home.svcStatus', d: 'home.svcStatusD', tint: '#F3E8FB', ink: '#5B2E86' },
]

export function Home() {
  const { t, chosen, setLang } = useI18n()
  const s = useSaathi()
  return (
    <>
      {!chosen && (
        <div className="nw-gate" role="dialog" aria-modal="true" aria-labelledby="gate-t">
          <div className="box">
            <h2 id="gate-t" className="display" style={{ fontSize: '1.9rem' }}>नमस्ते · Welcome</h2>
            <p className="muted" style={{ marginTop: 8 }}>अपनी भाषा चुनें<br />Choose your language</p>
            <div className="opts">
              <button type="button" lang="hi" onClick={() => setLang('hi')} autoFocus>हिंदी</button>
              <button type="button" lang="en" onClick={() => setLang('en')}>English</button>
            </div>
          </div>
        </div>
      )}

      <section className="nw-hero" aria-labelledby="hero-title">
        <div className="wrap">
          <div>
            <p className="eyebrow rise">{t('home.eyebrow')}</p>
            <h1 id="hero-title" className="display rise" style={{ marginTop: 10 }}>{t('home.title1')} <em>{t('home.title2')}</em></h1>
            <p className="lead rise">{t('home.lead')}</p>
            <div className="cta rise">
              <Btn variant="saffron" size="lg" icon={Mic} to="/network/saathi">{t('home.ctaTalk')}</Btn>
              <Btn variant="secondary" size="lg" icon={Search} to="/network/camps">{t('home.ctaCamps')}</Btn>
            </div>
            <p className="note rise"><Info size={16} aria-hidden />{t('home.note')}</p>
          </div>
          <div className="nw-stage rise" aria-hidden={false}>
            <HeroSun />
            <div className="frame"><img src={camp} alt={t('home.imgAlt')} width={1400} height={788} fetchPriority="high" /></div>
            <span className="nw-chip-float"><Stethoscope size={16} aria-hidden />{t('home.chip')}</span>
            <a className="orbwrap" {...linkProps('/network/saathi')}>
              <SaathiOrb as="div" state={s.status} level={s.level} size={64} />
              <span><b>{t('home.orbTitle')}</b><small>{t('home.orbBody')}</small></span>
            </a>
          </div>
        </div>
      </section>

      <section className="nw-section" aria-labelledby="svc-t" style={{ paddingTop: 32 }}>
        <div className="wrap">
          <Reveal><h2 id="svc-t" className="display">{t('home.svcTitle')}</h2></Reveal>
          <div className="nw-grid c3" style={{ marginTop: 28, gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))' }}>
            {SERVICES.map((c, i) => (
              <Reveal key={c.k} delay={i * 70}>
                <a className="nw-svc" {...linkProps(c.to)}>
                  <span className="art" style={{ background: c.tint, color: c.ink }}><c.icon size={34} aria-hidden /></span>
                  <h3>{t(c.k)}</h3>
                  <p>{t(c.d)}</p>
                  <span className="go">{t('home.open')}<ArrowRight size={18} aria-hidden /></span>
                </a>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="nw-section" aria-labelledby="how-t" style={{ paddingTop: 8 }}>
        <div className="wrap nw-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))', gap: 40, alignItems: 'center' }}>
          <Reveal>
            <h2 id="how-t" className="display">{t('home.howTitle')}</h2>
            <p className="lead muted" style={{ marginTop: 12 }}>{t('home.howLead')}</p>
          </Reveal>
          <Reveal delay={100}>
            <ol className="nw-steps">
              <li><div><b>{t('home.how1')}</b><span>{t('home.how1d')}</span></div></li>
              <li><div><b>{t('home.how2')}</b><span>{t('home.how2d')}</span></div></li>
              <li><div><b>{t('home.how3')}</b><span>{t('home.how3d')}</span></div></li>
            </ol>
          </Reveal>
        </div>
      </section>

      <section className="nw-section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <Reveal>
            <div className="nw-band">
              <p className="eyebrow" style={{ color: '#FFD9A0' }}>{t('home.bandEyebrow')}</p>
              <h2 className="display" style={{ marginTop: 8, maxWidth: '22ch' }}>{t('home.bandTitle')}</h2>
              <p style={{ marginTop: 12 }}>{t('home.bandBody')}</p>
              <ol className="nw-flow">
                <li><div><b>{t('home.flow1')}</b><span>{t('home.flow1d')}</span></div><span className="tag">{t('home.tagCommunity')}</span></li>
                <li><div><b>{t('home.flow2')}</b><span>{t('home.flow2d')}</span></div><span className="tag">{t('home.tagCommunity')}</span></li>
                <li><div><b>{t('home.flow3')}</b><span>{t('home.flow3d')}</span></div><span className="tag">{t('home.tagClinic')}</span></li>
                <li><div><b>{t('home.flow4')}</b><span>{t('home.flow4d')}</span></div><span className="tag">{t('home.tagClinic')}</span></li>
              </ol>
              <div style={{ marginTop: 26, position: 'relative', zIndex: 1, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Btn variant="secondary" to="/network/about">{t('home.bandCta')}</Btn>
                <Btn variant="ghost" to="/specialists">{t('nav.specialists')}</Btn>
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  )
}
