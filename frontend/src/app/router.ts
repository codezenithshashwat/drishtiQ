// Minimal history router: five screens do not need a routing library (react-router was removed for its advisories).
import { useEffect, useState } from 'react'

export type Route =
  | { name: 'landing' }
  | { name: 'worklist'; tab: string | null; q: string | null }
  | { name: 'new' }
  | { name: 'case'; id: string }
  | { name: 'report'; patient: string; caseId: string | null }
  | { name: 'about' }
  | { name: 'disagreements' }
  | { name: 'notFound' }

/** The landing page lives at "/"; the app at "/app/...". Code inside the app uses app paths ("/worklist", "/cases/X");
 * href() and navigate() add the prefix, so screens never spell it out. */
export const APP = '/app'
const APP_PATH = /^\/(worklist|new|about|disagreements|cases\/[^/]+|patients\/[^/]+\/report)$/

/** Public URL for an in-app path. "/" (the landing page), "#anchors" and "/app/..." are left as they are. */
export function href(to: string) {
  if (to === '/' || to.startsWith('#') || to === APP || to.startsWith(`${APP}/`) || to.startsWith(`${APP}?`)) return to
  return APP + to
}

/** Old deep links (before UI v3 the app was at "/") keep working: "/cases/X" -> "/app/cases/X". */
function redirectLegacy() {
  const { pathname, search, hash } = window.location
  if (APP_PATH.test(pathname)) window.history.replaceState({}, '', APP + pathname + search + hash)
}

export function parse(fullPath: string, search = ''): Route {
  const q = new URLSearchParams(search)
  if (fullPath === '/' || fullPath === '') return { name: 'landing' }
  if (fullPath !== APP && !fullPath.startsWith(`${APP}/`)) return { name: 'notFound' }
  const path = fullPath.slice(APP.length) || '/'
  let m
  if (path === '/' || path === '/worklist') return { name: 'worklist', tab: q.get('tab'), q: q.get('q') }
  if (path === '/new') return { name: 'new' }
  if (path === '/about') return { name: 'about' }
  if (path === '/disagreements') return { name: 'disagreements' }
  if ((m = path.match(/^\/cases\/([^/]+)$/))) return { name: 'case', id: decodeURIComponent(m[1]) }
  if ((m = path.match(/^\/patients\/([^/]+)\/report$/))) return { name: 'report', patient: decodeURIComponent(m[1]), caseId: q.get('case') }
  return { name: 'notFound' }
}

export function navigate(to: string) {
  if (!window.dispatchEvent(new CustomEvent('drishtiq:before-navigate', { cancelable: true }))) return
  window.history.pushState({}, '', href(to))
  window.dispatchEvent(new PopStateEvent('popstate'))
  window.scrollTo(0, 0)
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => { redirectLegacy(); return parse(window.location.pathname, window.location.search) })
  useEffect(() => {
    const on = () => setRoute(parse(window.location.pathname, window.location.search))
    window.addEventListener('popstate', on)
    return () => window.removeEventListener('popstate', on)
  }, [])
  return route
}

/** Anchor that navigates in-app (keeps open-in-new-tab working). */
export function linkProps(to: string) {
  return {
    href: href(to),
    onClick: (e: React.MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
      e.preventDefault()
      navigate(to)
    },
  }
}
