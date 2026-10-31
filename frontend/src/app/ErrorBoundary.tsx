import { Component, type ReactNode } from 'react'
import { Alert, Button } from '../design/components'

// A rendering fault in one screen shows a message instead of a blank page (a missing field once blanked the Case View).
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidUpdate(prev: { resetKey: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <Alert tone="danger" title="This screen could not be shown"
        action={<Button variant="secondary" compact onClick={() => window.location.reload()}>Reload</Button>}>
        Something in the data did not match what the screen expects ({this.state.error.message}). Reload the page; if it happens again, restart the app.
      </Alert>
    )
  }
}
