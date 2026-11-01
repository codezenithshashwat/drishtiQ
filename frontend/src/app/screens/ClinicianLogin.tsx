import { LockKeyhole } from 'lucide-react'
import { useState } from 'react'
import { Alert, Button, Field, Input } from '../../design/components'
import { ApiError, api, type Clinician } from '../api'
import { BrandLockup } from '../BrandMark'
import { linkProps } from '../router'

/** Specialist sign-in. The same account system as the rest of DrishtiQ; clinical access additionally needs an
 * ophthalmologist grant, which only an administrator can give. The backend enforces it on every request. */
export function ClinicianLogin({ reason, onSignedIn }: { reason?: string | null; onSignedIn: (u: Clinician) => void }) {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy || !identifier.trim() || !password) return
    setBusy(true); setError(null)
    try {
      await api.signIn(identifier.trim(), password)
      const me = await api.me()
      onSignedIn(me.user)
    } catch (x) {
      const err = x as ApiError
      setError(err.code === 'not_clinician' ? 'This account does not have specialist access. Ask an administrator to grant it.'
        : err.status === 429 ? 'Too many attempts. Wait a few minutes and try again.' : err.message || 'Sign-in failed.')
    } finally { setBusy(false) }
  }

  return (
    <div className="ds workspace grid min-h-screen place-items-center bg-surface-subtle px-4 py-10">
      <main id="main-content" tabIndex={-1} className="w-full max-w-[420px]">
        <a {...linkProps('/specialists')} className="mb-8 inline-block no-underline" aria-label="DrishtiQ for eye specialists"><BrandLockup /></a>
        <form onSubmit={submit} className="flex flex-col gap-5 rounded-card border border-border-default bg-surface-card p-6 shadow-card" aria-labelledby="login-title">
          <div>
            <p className="flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-text-secondary"><LockKeyhole size={14} aria-hidden />Specialist workspace</p>
            <h1 id="login-title" className="page-title mt-2">Sign in to Specialist Attention</h1>
            <p className="mt-2 text-secondary text-text-secondary">For authorised ophthalmologists. Your name is recorded with every decision you sign.</p>
          </div>
          {reason === 'session_expired' && !error && <Alert tone="info" title="Your session expired">Specialist sessions end after 30 minutes without activity. Please sign in again.</Alert>}
          {error && <Alert tone="danger" title="Not signed in">{error}</Alert>}
          <Field id="ident" label="Mobile number or email">
            <Input id="ident" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} disabled={busy} />
          </Field>
          <Field id="pw" label="Password">
            <Input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
          </Field>
          <Button type="submit" state={busy ? 'loading' : identifier.trim() && password ? 'default' : 'disabled'}>Sign in</Button>
          <p className="text-caption text-text-muted">Research prototype. Demo accounts are marked “prototype” and must not be used with real patient data.</p>
        </form>
        <p className="mt-6 text-center text-secondary"><a {...linkProps('/')} className="text-text-link">DrishtiQ for patients: Saathi and eye camps</a></p>
      </main>
    </div>
  )
}
