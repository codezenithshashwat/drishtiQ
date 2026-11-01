import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { ErrorBoundary } from '../app/ErrorBoundary'
import { Btn, Loading } from './components/ui'
import { I18nProvider, useI18n } from './i18n/I18n'
import type { Key } from './i18n/strings'
import { NetworkShell } from './NetworkShell'
import { useNetRoute, type NetRoute } from './netRouter'
import { SaathiProvider } from './saathi/SaathiProvider'
import { SessionProvider } from './session'
import { About } from './screens/About'
import { Awareness, Topic } from './screens/Awareness'
import { CampDetail, CampFinder } from './screens/Camps'
import { Home } from './screens/Home'
import { Login, Signup } from './screens/Auth'
import { Me } from './screens/Me'
import { Register, Status } from './screens/Register'
import { SaathiScreen } from './screens/SaathiScreen'
import './network.css'

// Staff tools are rarely opened by the public, so they load on demand.
const StaffLogin = lazy(() => import('./screens/staff/StaffLogin'))
const Worker = lazy(() => import('./screens/staff/Worker'))
const Organiser = lazy(() => import('./screens/staff/Organiser'))
const CampEditor = lazy(() => import('./screens/staff/CampEditor'))

const TITLE: Record<NetRoute['name'], Key> = {
  home: 'nav.home', saathi: 'nav.saathi', learn: 'nav.learn', topic: 'nav.learn', camps: 'nav.camps', camp: 'nav.camps', register: 'camps.register', status: 'status.title',
  signup: 'auth.signupTitle', login: 'auth.loginTitle', me: 'nav.me', staffLogin: 'foot.staff', worker: 'worker.title', organiser: 'org.title', organiserCamp: 'org.title', about: 'foot.about', notFound: 'nf.title',
}
const SIZES = ['md', 'lg', 'xl'] as const
const readSize = (): (typeof SIZES)[number] => { try { const v = localStorage.getItem('dqn.size'); return v === 'lg' || v === 'xl' ? v : 'md' } catch { return 'md' } }

export default function NetworkApp() {
  return <I18nProvider><SessionProvider><SaathiProvider><Frame /></SaathiProvider></SessionProvider></I18nProvider>
}

function Frame() {
  const route = useNetRoute()
  const { lang, t } = useI18n()
  const [size, setSize] = useState(readSize)
  const cycle = useCallback(() => setSize((s) => { const n = SIZES[(SIZES.indexOf(s) + 1) % 3]; try { localStorage.setItem('dqn.size', n) } catch { /* ignore */ } return n }), [])
  const path = window.location.pathname + window.location.search
  useEffect(() => { document.title = `${t(TITLE[route.name])} · DrishtiQ` })
  const first = useRef(true)  // move focus to the page only after in-app navigation; on first load the skip link must stay the first Tab stop
  useEffect(() => { if (first.current) { first.current = false; return } document.getElementById('nw-main')?.focus({ preventScroll: true }) }, [route.name, path])

  return (
    <div className="nw" data-lang={lang} data-size={size} lang={lang}>
      <NetworkShell route={route} size={size} onSize={cycle}>
        <ErrorBoundary resetKey={path}>
          <Suspense fallback={<div className="wrap" style={{ paddingTop: 40 }}><Loading /></div>}>
            {route.name === 'home' && <Home />}
            {route.name === 'saathi' && <SaathiScreen />}
            {route.name === 'learn' && <Awareness />}
            {route.name === 'topic' && <Topic key={route.slug} slug={route.slug} />}
            {route.name === 'camps' && <CampFinder key={`${route.pin}|${route.q}`} pin={route.pin} q={route.q} />}
            {route.name === 'camp' && <CampDetail key={route.id} id={route.id} />}
            {route.name === 'register' && <Register key={route.id} id={route.id} pin={route.pin} viaSaathi={route.viaSaathi} />}
            {route.name === 'status' && <Status key={`${route.ref}|${route.code}`} ref0={route.ref} code0={route.code} />}
            {route.name === 'signup' && <Signup />}
            {route.name === 'login' && <Login next={route.next} />}
            {route.name === 'me' && <Me />}
            {route.name === 'staffLogin' && <StaffLogin />}
            {route.name === 'worker' && <Worker />}
            {route.name === 'organiser' && <Organiser />}
            {route.name === 'organiserCamp' && <CampEditor key={String(route.id)} id={route.id} />}
            {route.name === 'about' && <About />}
            {route.name === 'notFound' && <NotFound />}
          </Suspense>
        </ErrorBoundary>
      </NetworkShell>
    </div>
  )
}

function NotFound() {
  const { t } = useI18n()
  return (
    <div className="wrap" style={{ padding: '64px 20px' }}>
      <div className="nw-empty"><h1 className="display" style={{ fontSize: '2rem' }}>{t('nf.title')}</h1><p className="muted" style={{ margin: '12px 0 24px' }}>{t('nf.body')}</p>
        <Btn size="lg" to="/">{t('nav.home')}</Btn></div>
    </div>
  )
}
