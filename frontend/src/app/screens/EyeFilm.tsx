import { Pause, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import film from '../../assets/landing/eye/eye-film.mp4'
import poster from '../../assets/landing/eye/eye-poster.jpg'

/** Decorative stock footage. Never used as a patient image or model input. */
export function EyeFilm() {
  const video = useRef<HTMLVideoElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const [preference, setPreference] = useState<boolean | null>(null)
  const [automatic, setAutomatic] = useState(false)
  const [inView, setInView] = useState(false)
  const [pageVisible, setPageVisible] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [failed, setFailed] = useState(false)
  const enabled = preference ?? automatic

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

  useEffect(() => { if (enabled && inView) setLoaded(true) }, [enabled, inView])
  useEffect(() => {
    const el = video.current
    if (!el || !loaded) return
    if (!enabled || !inView || !pageVisible || failed) { el.pause(); return }
    let current = true
    void el.play().catch(() => { if (current) setPlaying(false) })
    return () => { current = false; el.pause() }
  }, [enabled, inView, pageVisible, loaded, failed])

  return <div ref={frame} className="eye-film">
    <div className="eye-film-picture" aria-hidden="true">
      <img src={poster} width={1280} height={720} alt="" fetchPriority="high" />
      <video ref={video} src={loaded ? film : undefined} poster={poster} muted loop playsInline preload="none"
        tabIndex={-1} disablePictureInPicture onPlaying={() => setPlaying(true)} onPause={() => setPlaying(false)}
        onError={() => { setFailed(true); setPlaying(false) }} className={failed ? 'film-unavailable' : ''} />
    </div>
    <div className="eye-film-shade" aria-hidden="true" />
    <div className="film-controls">
      <span>Human eye · illustrative footage</span>
      <button type="button" disabled={failed} aria-label={playing ? 'Pause background eye video' : 'Play background eye video'}
        onClick={() => {
          if (playing) { setPreference(false); video.current?.pause() }
          else {
            setPreference(true)
            // A direct gesture also retries browsers that declined autoplay.
            if (loaded) void video.current?.play().catch(() => setPlaying(false))
          }
        }}>
        {playing ? <Pause size={15} aria-hidden /> : <Play size={15} aria-hidden />}
        {failed ? 'Still image' : playing ? 'Pause film' : 'Play film'}
      </button>
    </div>
  </div>
}
