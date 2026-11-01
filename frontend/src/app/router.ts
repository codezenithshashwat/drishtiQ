// Minimal history router: five screens do not need a routing library (react-router was removed for its advisories).
import { useEffect, useState } from 'react'

export type Route =
  | { name: 'specialists' }
  | { name: 'network' }
  | { name: 'worklist'; tab: string | null; q: string | null }
  | { name: 'new' }
  | { name: 'case'; id: string }
  | { name: 'report'; patient: string; caseId: string | null }
  | { name: 'about' }
  | { name: 'disagreements' }
  | { name: 'login'; next: string | null }
  | { name: 'notFound' }

/** One DrishtiQ platform, one router:
 *  - "/" and "/network/..."  the patient experience (home, Saathi, camps, learn, status); own route table in src/network/netRouter.ts
 *  - "/specialists"          the professional entry (the cinematic page) leading into the specialist workspace
 *  - "/app/..."              the specialist workspace. Code inside it uses app paths ("/worklist", "/cases/X"); href() and
 *                            navigate() add the prefix, so screens never spell it out. */
export const APP = '/app'
export const NETWORK = '/network'
export const SPECIALISTS = '/specialists'
const isNetwork = (p: string) => p === NETWORK || p.startsWith(`${NETWORK}/`)
const APP_PATH = /^\/(worklist|new|about|disagreements|cases\/[^/]+|patients\/[^/]+\/report)$/
const PUBLIC = new Set(['/', SPECIALISTS])

/** Public URL for an in-app path. "/", "/specialists", "#anchors", "/network/..." and "/app/..." are left as they are. */
export function href(to: string) {
  const path = to.split(/[?#]/)[0]
  if (PUBLIC.has(path) || to.startsWith('#') || isNetwork(path) || path === APP || to.startsWith(`${APP}/`) || to.startsWith(`${APP}?`)) return to
  return APP + to
}

/** Old addresses keep working, each with a single replaceState (never a chain, so no loops):
 *  "/cases/X" -> "/app/cases/X" (before UI v3), "/network" -> "/" (the patient home moved), "/technology" -> "/specialists". */
export function canonical(pathname: string): string | null {
  if (APP_PATH.test(pathname)) return APP + pathname
  if (pathname === NETWORK || pathname === `${NETWORK}/`) return '/'
  if (pathname === '/technology' || pathname === `${SPECIALISTS}/`) return SPECIALISTS
  return null
}
function redirectLegacy() {
  const { pathname, search, hash } = window.location
  const to = canonical(pathname)
  if (to && to !== pathname) window.history.replaceState({}, '', to + search + hash)
}

export function parse(fullPath: string, search = ''): Route {
  const q = new URLSearchParams(search)
  if (fullPath === '/' || fullPath === '' || isNetwork(fullPath)) return { name: 'network' }
  if (fullPath === SPECIALISTS || fullPath === '/technology') return { name: 'specialists' }
  if (fullPath !== APP && !fullPath.startsWith(`${APP}/`)) return { name: 'notFound' }
  const path = fullPath.slice(APP.length) || '/'
  let m
  if (path === '/' || path === '/worklist') return { name: 'worklist', tab: q.get('tab'), q: q.get('q') }
  if (path === '/new') return { name: 'new' }
  if (path === '/about') return { name: 'about' }
  if (path === '/disagreements') return { name: 'disagreements' }
  if (path === '/login') return { name: 'login', next: q.get('next') }
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
