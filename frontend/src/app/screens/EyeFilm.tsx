import { useEffect, useRef, useState } from 'react'
import film from '../../assets/landing/eye/eye-film.mp4'
import poster from '../../assets/landing/eye/eye-poster.jpg'

/** Decorative film with a still fallback and automatic motion preferences. */
export function EyeFilm() {
  const video = useRef<HTMLVideoElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const [automatic, setAutomatic] = useState(false)
  const [inView, setInView] = useState(false)
  const [pageVisible, setPageVisible] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
    const update = () => setAutomatic(!motion.matches && !connection?.saveData)
    const visibility = () => setPageVisible(!document.hidden)
    update(); visibility()
    motion.addEventListener('change', update)
    document.addEventListener('visibilitychange', visibility)
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0 })
    if (frame.current) observer.observe(frame.current)
    return () => { motion.removeEventListener('change', update); document.removeEventListener('visibilitychange', visibility); observer.disconnect() }
  }, [])

  useEffect(() => { if (automatic && inView) setLoaded(true) }, [automatic, inView])
  useEffect(() => {
    const el = video.current
    if (!el || !loaded) return
    if (!automatic || !inView || !pageVisible || failed) { el.pause(); return }
    void el.play().catch(() => { /* The poster remains visible when autoplay is unavailable. */ })
    return () => el.pause()
  }, [automatic, inView, pageVisible, loaded, failed])

  return <div ref={frame} className="eye-film" aria-hidden="true">
    <div className="eye-film-picture">
      <img src={poster} width={1280} height={720} alt="" fetchPriority="high" />
      <video ref={video} src={loaded ? film : undefined} poster={poster} muted loop playsInline preload="none"
        tabIndex={-1} disablePictureInPicture onError={() => setFailed(true)} className={failed ? 'film-unavailable' : ''} />
    </div>
    <div className="eye-film-shade" />
  </div>
}
