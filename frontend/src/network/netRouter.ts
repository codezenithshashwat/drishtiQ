// Route table for DrishtiQ Network. Navigation itself (navigate, linkProps) is the app's own router; this file only
// understands what lies under /network.
import { useEffect, useState } from 'react'

export type NetRoute =
  | { name: 'home' }
  | { name: 'saathi' }
  | { name: 'learn' }
  | { name: 'topic'; slug: string }
  | { name: 'camps'; pin: string | null; q: string | null }
  | { name: 'camp'; id: number }
  | { name: 'register'; id: number; pin: string | null; viaSaathi: boolean }
  | { name: 'status'; ref: string | null; code: string | null }
  | { name: 'signup' }
  | { name: 'login'; next: string | null }
  | { name: 'me' }
  | { name: 'staffLogin' }
  | { name: 'worker' }
  | { name: 'organiser' }
  | { name: 'organiserCamp'; id: number | 'new' }
  | { name: 'about' }
  | { name: 'notFound' }

export function parseNet(path: string, search = ''): NetRoute {
  const q = new URLSearchParams(search)
  const p = path.replace(/\/+$/, '') || '/'
  let m
  if (p === '/' || p === '/network') return { name: 'home' }  // "/" is the DrishtiQ home; "/network" stays as an alias
  if (p === '/network/saathi') return { name: 'saathi' }
  if (p === '/network/learn') return { name: 'learn' }
  if ((m = p.match(/^\/network\/learn\/([a-z0-9-]+)$/))) return { name: 'topic', slug: m[1] }
  if (p === '/network/camps') return { name: 'camps', pin: q.get('pin'), q: q.get('q') }
  if ((m = p.match(/^\/network\/camps\/(\d+)$/))) return { name: 'camp', id: Number(m[1]) }
  if ((m = p.match(/^\/network\/camps\/(\d+)\/register$/))) return { name: 'register', id: Number(m[1]), pin: q.get('pin'), viaSaathi: q.get('via') === 'saathi' }
  if (p === '/network/status') return { name: 'status', ref: q.get('ref'), code: q.get('code') }
  if (p === '/network/signup') return { name: 'signup' }
  if (p === '/network/login') return { name: 'login', next: q.get('next') }
  if (p === '/network/me') return { name: 'me' }
  if (p === '/network/staff') return { name: 'staffLogin' }
  if (p === '/network/worker') return { name: 'worker' }
  if (p === '/network/organiser') return { name: 'organiser' }
  if (p === '/network/organiser/camps/new') return { name: 'organiserCamp', id: 'new' }
  if ((m = p.match(/^\/network\/organiser\/camps\/(\d+)$/))) return { name: 'organiserCamp', id: Number(m[1]) }
  if (p === '/network/about') return { name: 'about' }
  return { name: 'notFound' }
}

export function useNetRoute(): NetRoute {
  const [route, setRoute] = useState(() => parseNet(window.location.pathname, window.location.search))
  useEffect(() => {
    const on = () => setRoute(parseNet(window.location.pathname, window.location.search))
    window.addEventListener('popstate', on)
    return () => window.removeEventListener('popstate', on)
  }, [])
  return route
}
