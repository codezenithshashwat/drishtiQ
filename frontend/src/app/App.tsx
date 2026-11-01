import { SearchX } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, EmptyState } from '../design/components'
import { api, type CaseDetail, type Glossary } from './api'
import { BRAND } from './brand'
import { ErrorBoundary } from './ErrorBoundary'
import { eyeName } from './format'
import { navigate, useRoute } from './router'
import { About } from './screens/About'
import { CaseView } from './screens/CaseView'
import { Disagreements } from './screens/Disagreements'
import { Landing } from './screens/Landing'
import { NewScreening } from './screens/NewScreening'
import { Report } from './screens/Report'
import { Worklist } from './screens/Worklist'
import { Shell, type Crumb } from './Shell'

export default function App() {
  const route = useRoute()
  const [glossary, setGlossary] = useState<Glossary | null>(null)
  const [version, setVersion] = useState<string>()
  const [stale, setStale] = useState<string | null>(null)
  const [caseCrumb, setCaseCrumb] = useState<CaseDetail | null>(null)

  useEffect(() => {
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
  }, [])
  const onCase = useCallback((c: CaseDetail) => setCaseCrumb(c), [])

  const titles: Record<string, string> = { landing: BRAND, worklist: 'Worklist', new: 'New screening', about: 'About the model', disagreements: 'Disagreements', notFound: 'Not found' }
  const worklistTitle = route.name === 'worklist' && route.tab === 'reviewed' ? 'History' : 'Worklist'
  let crumbs: Crumb[]
  if (route.name === 'case') {
    const c = caseCrumb?.id === route.id ? caseCrumb : null
    crumbs = [{ label: 'Worklist', to: '/worklist' }, { label: c ? `${c.patient_ref} · ${eyeName(c.eye)}` : route.id }]
  } else if (route.name === 'report') {
    crumbs = [{ label: 'Worklist', to: '/worklist' }, ...(route.caseId ? [{ label: route.caseId, to: `/cases/${route.caseId}` }] : []), { label: `Report · ${route.patient}` }]
  } else {
    crumbs = [{ label: route.name === 'worklist' ? worklistTitle : titles[route.name] }]
  }
  useEffect(() => { document.title = `${crumbs[crumbs.length - 1].label} · ${BRAND}` })
  const routePath = window.location.pathname
  useEffect(() => {
    document.getElementById('main-content')?.focus({ preventScroll: true })
  }, [routePath])

  if (route.name === 'landing') return <Landing />

  return (
    <Shell route={route} crumbs={crumbs} version={version}>
      {stale && (
        <div className="mb-6"><Alert tone="danger" title="The screening service needs attention">
          Saving cases or reviews may be unavailable. Check the local service before continuing.
          <details className="mt-2"><summary className="cursor-pointer">Technical details</summary>{stale}</details>
        </Alert></div>
      )}
      <ErrorBoundary resetKey={window.location.pathname}>
      {route.name === 'worklist' && <Worklist key={`${route.tab}|${route.q}`} initialTab={route.tab} initialQuery={route.q} />}
      {route.name === 'new' && <NewScreening />}
      {route.name === 'case' && <CaseView key={route.id} id={route.id} glossary={glossary} onLoaded={onCase} />}
      {route.name === 'report' && <Report key={route.patient} patient={route.patient} caseId={route.caseId} />}
      {route.name === 'about' && <About />}
      {route.name === 'disagreements' && <Disagreements />}
      {route.name === 'notFound' && (
        <EmptyState icon={SearchX} title="Page not found" body="The address does not match any screen." action={<Button onClick={() => navigate('/worklist')}>Go to the worklist</Button>} />
      )}
      </ErrorBoundary>
    </Shell>
  )
}
