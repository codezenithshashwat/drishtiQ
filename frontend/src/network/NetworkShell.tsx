import { BookOpenText, Home, LogIn, LogOut, MapPinned, Mic, UserRound, type LucideIcon } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { BrandMark } from '../app/BrandMark'
import { linkProps } from '../app/router'
import { net } from './api'
import { SaathiOrb } from './components/SaathiOrb'
import { cx } from './components/ui'
import { useI18n } from './i18n/I18n'
import type { Key } from './i18n/strings'
import type { NetRoute } from './netRouter'
import { useSaathi } from './saathi/SaathiProvider'
import { useSession } from './session'

type Item = { to: string; key: Key; icon: LucideIcon; on: (r: NetRoute) => boolean; saathi?: boolean }
const ITEMS: Item[] = [
  { to: '/', key: 'nav.home', icon: Home, on: (r) => r.name === 'home' },
  { to: '/network/camps', key: 'nav.camps', icon: MapPinned, on: (r) => r.name === 'camps' || r.name === 'camp' || r.name === 'register' },
  { to: '/network/saathi', key: 'nav.saathi', icon: Mic, on: (r) => r.name === 'saathi', saathi: true },
  { to: '/network/learn', key: 'nav.learn', icon: BookOpenText, on: (r) => r.name === 'learn' || r.name === 'topic' },
  { to: '/network/me', key: 'nav.me', icon: UserRound, on: (r) => r.name === 'me' || r.name === 'login' || r.name === 'signup' || r.name === 'status' },
]

export function NetworkShell({ route, size, onSize, children }: { route: NetRoute; size: 'md' | 'lg' | 'xl'; onSize: () => void; children: ReactNode }) {
  const { t, lang, setLang } = useI18n()
  const { user, logout } = useSession()
  const s = useSaathi()
  const [demo, setDemo] = useState(false)
  useEffect(() => { net.config().then((c) => setDemo(c.demo_mode), () => {}) }, [])
  const home = user && user.role === 'health_worker' ? '/network/worker' : user && (user.role === 'organiser' || user.role === 'admin') ? '/network/organiser' : '/network/me'

  return (
    <>
      <a className="skip" href="#nw-main" onClick={(e) => { e.preventDefault(); document.getElementById('nw-main')?.focus() }}>{t('nav.skip')}</a>
      {demo && <div className="nw-banner" role="note">{t('shell.demoBanner')}</div>}
      <header className="nw-top">
        <div className="wrap">
          <a className="nw-brand" {...linkProps('/')} aria-label={t('nav.brandHome')}>
            <BrandMark size={38} />
            <span><b>DrishtiQ</b></span>
          </a>
          <nav className="nw-nav" aria-label={t('nav.main')}>
            {ITEMS.map((i) => <a key={i.to} {...linkProps(i.to)} aria-current={i.on(route) ? 'page' : undefined}>{t(i.key)}</a>)}
          </nav>
          <div className="nw-lang" role="group" aria-label={t('nav.language')}>
            <button type="button" lang="hi" aria-pressed={lang === 'hi'} onClick={() => setLang('hi')}>हिंदी</button>
            <button type="button" lang="en" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
          </div>
          <button type="button" className="nw-btn secondary sm" onClick={onSize} aria-label={t('nav.textSize')} title={t('nav.textSize')} style={{ minWidth: 48, padding: '0 12px' }}>
            <span aria-hidden style={{ fontWeight: 700 }}>{size === 'md' ? 'A' : size === 'lg' ? 'A+' : 'A++'}</span>
          </button>
          <span className="acct" style={{ gap: 8, alignItems: 'center' }}>
            {user ? (
              <>
                <a className="nw-btn secondary sm" {...linkProps(home)}><UserRound size={18} aria-hidden />{user.name.split(' ')[0]}</a>
                <button type="button" className="nw-btn ghost sm" onClick={() => { void logout() }} aria-label={t('nav.logout')}><LogOut size={18} aria-hidden /></button>
              </>
            ) : <a className="nw-btn secondary sm" {...linkProps('/network/login')}><LogIn size={18} aria-hidden />{t('nav.login')}</a>}
          </span>
        </div>
      </header>

      <main id="nw-main" className="nw-main" tabIndex={-1}>{children}</main>

      <footer className="nw-foot">
        <div className="wrap">
          <div>
            <p><b>{t('foot.tagline')}</b></p>
            <p style={{ marginTop: 8 }}>{t('foot.disclaimer')}</p>
          </div>
          <nav aria-label={t('foot.links')}>
            <a {...linkProps('/network/about')}>{t('foot.about')}</a>
            <a {...linkProps('/specialists')}>{t('foot.ai')}</a>
            <a {...linkProps('/network/staff')}>{t('foot.staff')}</a>
          </nav>
        </div>
      </footer>

      <nav className="nw-tabs" aria-label={t('nav.main')}>
        {ITEMS.map((i) => (
          <a key={i.to} {...linkProps(i.to)} aria-current={i.on(route) ? 'page' : undefined}>
            {i.saathi
              ? <span style={{ width: 44, height: 44, borderRadius: '50%', display: 'grid', placeItems: 'center', background: 'linear-gradient(145deg,#3E5DB5,#1C3068)', boxShadow: '0 6px 16px rgba(38,63,131,.4)', marginTop: -16, color: '#fff' }}><i.icon size={22} aria-hidden /></span>
              : <i.icon size={22} aria-hidden />}
            <span>{t(i.key)}</span>
          </a>
        ))}
      </nav>

      {route.name !== 'saathi' && (
        <div className={cx('nw-fab', s.status === 'idle' && 'idle')}>
          {s.status === 'speaking' && <button type="button" className="stop" onClick={s.stopSpeaking}>{t('saathi.stop')}</button>}
          <span className="tip">{s.status === 'idle' ? t('fab.tip') : t(`saathi.state.${s.status}` as Key)}</span>
          <a {...linkProps('/network/saathi')} aria-label={t('fab.label')} style={{ borderRadius: '50%', display: 'block' }}>
            <SaathiOrb as="div" state={s.status} level={s.level} size={72} />
          </a>
        </div>
      )}
    </>
  )
}
