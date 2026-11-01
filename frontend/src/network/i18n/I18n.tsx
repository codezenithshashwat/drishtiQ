import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { NetError, type Camp, type Lang } from '../api'
import { en, hi, type Key } from './strings'

const KEY = 'dqn.lang'
const read = (): Lang | null => { try { const v = localStorage.getItem(KEY); return v === 'hi' || v === 'en' ? v : null } catch { return null } }

type Ctx = {
  lang: Lang
  chosen: boolean
  setLang: (l: Lang) => void
  t: (k: Key, vars?: Record<string, string | number>) => string
  when: (iso: string, withTime?: boolean) => string
  campTitle: (c: Camp) => string
  errMsg: (e: unknown) => string
}
const I18n = createContext<Ctx | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const stored = read()
  const [lang, setL] = useState<Lang>(stored ?? (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('hi') ? 'hi' : 'en'))
  const [chosen, setChosen] = useState(stored !== null)
  const setLang = useCallback((l: Lang) => { setL(l); setChosen(true); try { localStorage.setItem(KEY, l) } catch { /* private mode */ } }, [])
  const value = useMemo<Ctx>(() => {
    const dict = lang === 'hi' ? hi : en
    const t: Ctx['t'] = (k, vars) => {
      let s: string = dict[k] ?? en[k]
      if (vars) for (const [a, b] of Object.entries(vars)) s = s.split(`{${a}}`).join(String(b))
      return s
    }
    const loc = lang === 'hi' ? 'hi-IN' : 'en-IN'
    const when = (iso: string, withTime = true) => {
      const d = new Date(iso)
      const day = new Intl.DateTimeFormat(loc, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(d)
      if (!withTime) return day
      return `${day}, ${new Intl.DateTimeFormat(loc, { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' }).format(d)}`
    }
    const errMsg = (e: unknown) => {
      const code = e instanceof NetError ? e.code : 'generic'
      const k = `err.${code}` as Key
      return k in en ? t(k) : t('err.generic')
    }
    return { lang, chosen, setLang, t, when, campTitle: (c) => c.title[lang] || c.title.en, errMsg }
  }, [lang, chosen, setLang])
  useEffect(() => { document.documentElement.lang = lang === 'hi' ? 'hi' : 'en' }, [lang])
  return <I18n.Provider value={value}>{children}</I18n.Provider>
}

export function useI18n(): Ctx {
  const c = useContext(I18n)
  if (!c) throw new Error('useI18n outside provider')
  return c
}
