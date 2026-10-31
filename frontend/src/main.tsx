import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './design/ds.css'
import App from './app/App'

// Component gallery for design review; loaded lazily so it adds nothing to the app bundle.
const DesignSystem = lazy(() => import('./design/DesignSystem'))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {window.location.pathname === '/design-system' ? <Suspense fallback={null}><DesignSystem /></Suspense> : <App />}
  </StrictMode>,
)

// Accessibility audit on demand (?axe=1): axe-core is a separate lazy chunk that everyday use never loads.
// Results land in window.__axe for the audit script (results/a11y.json).
if (new URLSearchParams(window.location.search).has('axe')) {
  const w = window as unknown as { __axe: unknown; __runAxe: () => Promise<void> }
  // Re-runnable so the audit script can check states reached by clicking (tabs, language switch).
  w.__runAxe = () => { w.__axe = null; return import('axe-core').then(async ({ default: axe }) => {
    const r = await axe.run(document, { resultTypes: ['violations'] })
    w.__axe = r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
      targets: v.nodes.slice(0, 3).map((n) => String(n.target)) }))
  }) }
  window.setTimeout(() => { void w.__runAxe() }, 2500)
}
