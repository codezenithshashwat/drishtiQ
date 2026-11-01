import { useEffect } from 'react'

/** Protect local drafts on app navigation and page close; no patient data is persisted here. */
export function useUnsavedChanges(dirty: boolean, message: string) {
  useEffect(() => {
    if (!dirty) return
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    const beforeNavigate = (event: Event) => { if (!window.confirm(message)) event.preventDefault() }
    window.addEventListener('beforeunload', beforeUnload)
    window.addEventListener('drishtiq:before-navigate', beforeNavigate)
    return () => {
      window.removeEventListener('beforeunload', beforeUnload)
      window.removeEventListener('drishtiq:before-navigate', beforeNavigate)
    }
  }, [dirty, message])
}
