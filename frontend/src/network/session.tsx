import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { net, type User } from './api'

type S = { user: User | null; ready: boolean; setUser: (u: User | null) => void; logout: () => Promise<void> }
const Ctx = createContext<S | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let live = true
    net.me().then((r) => { if (live) setUser(r.user) }, () => { /* offline: stay a guest */ }).finally(() => { if (live) setReady(true) })
    return () => { live = false }
  }, [])
  const logout = useCallback(async () => { try { await net.logout() } finally { setUser(null) } }, [])
  const value = useMemo(() => ({ user, ready, setUser, logout }), [user, ready, logout])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSession(): S {
  const c = useContext(Ctx)
  if (!c) throw new Error('useSession outside provider')
  return c
}
