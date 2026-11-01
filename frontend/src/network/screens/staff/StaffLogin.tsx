import { ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { navigate } from '../../../app/router'
import { net } from '../../api'
import { Notice, PageHead } from '../../components/ui'
import { useI18n } from '../../i18n/I18n'
import { useSession } from '../../session'
import { homeFor, LoginForm } from '../Auth'

const DEMO = [
  { role: 'health_worker', id: '9000000001', pw: 'Demo@Worker1' },
  { role: 'organiser', id: '9000000002', pw: 'Demo@Organiser1' },
  { role: 'admin', id: '9000000003', pw: 'Demo@Admin1' },
]

export default function StaffLogin() {
  const { t } = useI18n()
  const { user } = useSession()
  const [demo, setDemo] = useState(false)
  useEffect(() => { net.config().then((c) => setDemo(c.demo_mode), () => {}) }, [])
  useEffect(() => { if (user && user.role !== 'user') navigate(homeFor(user)) }, [user])
  return (
    <>
      <PageHead eyebrow={t('foot.staff')} title={t('staff.title')} lead={t('staff.lead')} />
      <div className="wrap" style={{ maxWidth: 600, display: 'grid', gap: 20, paddingBottom: 64 }}>
        <Notice tone="info" title={t('staff.noSwitchTitle')}>{t('staff.noSwitch')}</Notice>
        <LoginForm onDone={(u) => navigate(homeFor(u))} idLabel={t('staff.id')} />
        {demo && (
          <section className="nw-card tint" style={{ display: 'grid', gap: 10 }} aria-labelledby="demo-t">
            <h2 id="demo-t" style={{ fontSize: '1.1rem', display: 'flex', gap: 8, alignItems: 'center' }}><ShieldCheck size={20} aria-hidden />{t('staff.demoTitle')}</h2>
            <p className="muted" style={{ fontSize: '.92rem' }}>{t('staff.demoBody')}</p>
            <ul style={{ display: 'grid', gap: 6, fontFamily: 'ui-monospace, Consolas, monospace', fontSize: '.9rem' }}>
              {DEMO.map((d) => <li key={d.id}><b>{d.role}</b>: {d.id} / {d.pw}</li>)}
            </ul>
          </section>
        )}
      </div>
    </>
  )
}
