import { Building2, CalendarDays, MapPin } from 'lucide-react'
import { cx, Btn, StateBadge, VerificationBadge } from './ui'
import type { Camp } from '../api'
import { useI18n } from '../i18n/I18n'

export function placeLine(c: Camp) { return [c.place.village || c.place.label, c.place.district].filter(Boolean).join(', ') }

export function CampCard({ camp }: { camp: Camp }) {
  const { t, when, campTitle } = useI18n()
  const dim = camp.state === 'expired' || camp.state === 'cancelled'
  return (
    <article className={cx('nw-camp', dim && 'dim')} aria-labelledby={`camp-${camp.id}`}>
      {camp.is_demo && <span className="nw-demo-ribbon" aria-hidden>{t('badge.demoRibbon')}</span>}
      <div className="tags">
        <VerificationBadge v={camp.verification} />
        <StateBadge s={camp.state} />
        {camp.match === 'nearby' && <span className="nw-badge neutral">{t('camps.nearbyArea')}</span>}
        {camp.match === 'exact' && <span className="nw-badge neutral">{t('camps.yourPin')}</span>}
      </div>
      <h3 id={`camp-${camp.id}`}>{campTitle(camp)}</h3>
      <div className="meta">
        <div><CalendarDays size={18} aria-hidden /><span>{when(camp.starts_at)}</span></div>
        <div><MapPin size={18} aria-hidden /><span>{placeLine(camp)} · PIN {camp.place.pin}</span></div>
        <div><Building2 size={18} aria-hidden /><span>{camp.organiser.name}</span></div>
      </div>
      <div className="act">
        <Btn variant="secondary" size="sm" to={`/network/camps/${camp.id}`}>{t('camps.details')}</Btn>
        {camp.state === 'open' && <Btn size="sm" to={`/network/camps/${camp.id}/register`}>{t('camps.register')}</Btn>}
      </div>
    </article>
  )
}
