import { SearchX } from 'lucide-react'
import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Alert, Button, EmptyState, Skeleton } from '../design/components'
import { AUTH_EVENT, api, type CaseDetail, type Clinician, type Glossary } from './api'
import { BRAND } from './brand'
import { ErrorBoundary } from './ErrorBoundary'
import { eyeName } from './format'
import { navigate, useRoute } from './router'
import { ClinicianLogin } from './screens/ClinicianLogin'
import { Shell, type Crumb } from './Shell'

// One DrishtiQ platform. The patient experience ("/", "/network/...") is the front door, so it is what a phone downloads
// first; the professional entry and the specialist workspace load only when someone opens them.
const NetworkApp = lazy(() => import('../network/NetworkApp'))
const Landing = lazy(() => import('./screens/Landing').then((m) => ({ default: m.Landing })))
const About = lazy(() => import('./screens/About').then((m) => ({ default: m.About })))
const CaseView = lazy(() => import('./screens/CaseView').then((m) => ({ default: m.CaseView })))
const Disagreements = lazy(() => import('./screens/Disagreements').then((m) => ({ default: m.Disagreements })))
const NewScreening = lazy(() => import('./screens/NewScreening').then((m) => ({ default: m.NewScreening })))
const Report = lazy(() => import('./screens/Report').then((m) => ({ default: m.Report })))
const Worklist = lazy(() => import('./screens/Worklist').then((m) => ({ default: m.Worklist })))

export default function App() {
  const route = useRoute()
  const workspace = route.name !== 'network' && route.name !== 'specialists'
  const [glossary, setGlossary] = useState<Glossary | null>(null)
  const [version, setVersion] = useState<string>()
  const [stale, setStale] = useState<string | null>(null)
  const [caseCrumb, setCaseCrumb] = useState<CaseDetail | null>(null)
  // undefined = checking, null = not signed in as a clinician. The UI gate is a convenience; the server enforces access.
  const [clinician, setClinician] = useState<Clinician | null | undefined>(undefined)
  const [authReason, setAuthReason] = useState<string | null>(null)

  useEffect(() => {
    if (!workspace || clinician !== undefined) return
    api.me().then((m) => setClinician(m.user), () => setClinician(null))
  }, [workspace, clinician])
  useEffect(() => {
    const on = (e: Event) => { setAuthReason((e as CustomEvent<{ code: string | null }>).detail?.code ?? null); setClinician(null) }
    window.addEventListener(AUTH_EVENT, on)
    return () => window.removeEventListener(AUTH_EVENT, on)
  }, [])
  const signedIn = useCallback((u: Clinician) => {
    setClinician(u); setAuthReason(null)
    if (route.name === 'login') navigate(route.next && route.next.startsWith('/') && !route.next.startsWith('//') ? route.next : '/worklist')
  }, [route])
  useEffect(() => { if (clinician && route.name === 'login') navigate('/worklist') }, [clinician, route])
  const signOut = useCallback(() => { void api.signOut().finally(() => { setClinician(null); setAuthReason(null); navigate('/specialists') }) }, [])

  useEffect(() => {
    if (!workspace || !clinician) return  // patient pages never call the clinical API; nor does the sign-in screen
    api.glossary().then(setGlossary, () => setGlossary(null))
    // The backend must run the same commit this page was built from, and the code on disk must not have moved on.
    const check = () => api.version().then((v) => {
      setVersion(v.model_version)
      if (v.commit !== __BUILD_COMMIT__ || v.commit_on_disk !== v.commit) {
        setStale(`Page built from ${__BUILD_COMMIT__}, backend running ${v.commit ?? 'unknown'}, code on disk ${v.commit_on_disk ?? 'unknown'}.`)
      } else setStale(null)
    }, () => setStale('The backend did not answer /api/version; it may be an older version or not running.'))
    check()
    const t = window.setInterval(check, 60_000)
    return () => window.clearInterval(t)
  }, [workspace, clinician])
  const onCase = useCallback((c: CaseDetail) => setCaseCrumb(c), [])

  const titles: Record<string, string> = { specialists: 'For eye specialists', network: BRAND, worklist: 'Specialist Attention', new: 'New screening', about: 'About the model', disagreements: 'Disagreements', login: 'Specialist sign-in', notFound: 'Not found' }
  const worklistTitle = 'Specialist Attention'
  let crumbs: Crumb[]
  if (route.name === 'case') {
    const c = caseCrumb?.id === route.id ? caseCrumb : null
    crumbs = [{ label: 'Specialist Attention', to: '/worklist' }, { label: c ? `${c.patient_ref} · ${eyeName(c.eye)}` : route.id }]
  } else if (route.name === 'report') {
    crumbs = [{ label: 'Specialist Attention', to: '/worklist' }, ...(route.caseId ? [{ label: route.caseId, to: `/cases/${route.caseId}` }] : []), { label: `Report · ${route.patient}` }]
  } else {
    crumbs = [{ label: route.name === 'worklist' ? worklistTitle : titles[route.name] }]
  }
  useEffect(() => { if (workspace) document.title = `${crumbs[crumbs.length - 1].label} · ${BRAND}` })
  const routePath = window.location.pathname
  useEffect(() => {
    document.getElementById('main-content')?.focus({ preventScroll: true })
  }, [routePath])

  if (route.name === 'specialists') return <Suspense fallback={<div className="ds landing" style={{ minHeight: '100vh' }} aria-busy="true" />}><Landing /></Suspense>
  if (route.name === 'network') return <Suspense fallback={<div style={{ minHeight: '100vh', background: '#FBF7F0' }} aria-busy="true" />}><NetworkApp /></Suspense>
  if (clinician === undefined) return <div className="ds workspace min-h-screen bg-surface-subtle" aria-busy="true"><span className="sr-only">Checking your specialist session</span></div>
  if (clinician === null || route.name === 'login') return <ClinicianLogin key={clinician === null ? 'out' : 'in'} reason={authReason} onSignedIn={signedIn} />

  return (
    <Shell route={route} crumbs={crumbs} version={version} clinician={clinician} onSignOut={signOut}>
      {stale && (
        <div className="mb-6"><Alert tone="danger" title="The screening service needs attention">
          Saving cases or reviews may be unavailable. Check the local service before continuing.
          <details className="mt-2"><summary className="cursor-pointer">Technical details</summary>{stale}</details>
        </Alert></div>
      )}
      <ErrorBoundary resetKey={window.location.pathname}>
      <Suspense fallback={<div aria-busy="true" className="flex flex-col gap-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-64" /></div>}>
      {route.name === 'worklist' && <Worklist key={`${route.tab}|${route.q}`} initialTab={route.tab} initialQuery={route.q} />}
      {route.name === 'new' && <NewScreening />}
      {route.name === 'case' && <CaseView key={route.id} id={route.id} glossary={glossary} onLoaded={onCase} />}
      {route.name === 'report' && <Report key={route.patient} patient={route.patient} caseId={route.caseId} />}
      {route.name === 'about' && <About />}
      {route.name === 'disagreements' && <Disagreements />}
      {route.name === 'notFound' && (
        <EmptyState icon={SearchX} title="Page not found" body="The address does not match any screen." action={<Button onClick={() => navigate('/worklist')}>Go to the worklist</Button>} />
      )}
      </Suspense>
      </ErrorBoundary>
    </Shell>
  )
}
