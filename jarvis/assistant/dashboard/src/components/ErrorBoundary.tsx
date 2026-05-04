/**
 * ErrorBoundary — catches render-time exceptions in any child subtree
 * and shows a minimal fallback UI instead of crashing the whole kiosk
 * to a blank screen.
 *
 * Why we have this:
 *   The dashboard is a kiosk display on the Jetson. A render error in
 *   any avatar component (or any other deep widget) used to bubble up
 *   to React's default handler, which unmounts the entire tree —
 *   leaving a literally empty white screen with no recovery path.
 *   The user has to SSH in and restart the browser to fix it.
 *
 *   With this boundary wrapping the App tree, a render error stays
 *   contained: the broken subtree shows a fallback, and after a short
 *   delay the boundary self-resets so the next render attempt can
 *   succeed (transient errors recover automatically).
 *
 *   This is React's only mechanism for catching render-time exceptions
 *   — class components are required. There is no functional-component
 *   equivalent yet.
 *
 * Limitations (worth knowing):
 *   - Does NOT catch errors in event handlers (those propagate to
 *     window.onerror; not our problem here, kiosk has no devtools).
 *   - Does NOT catch errors in async code / promises / setTimeout.
 *   - Does NOT catch errors during SSR (we don't SSR).
 *   - Resets only on auto-timeout or manual reload — does not auto-reset
 *     on prop change because that would mask a persistent bug as flicker.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Optional custom fallback render. Receives the error so it can format it. */
  fallback?: (error: Error, reset: () => void) => ReactNode
  /** Auto-reset after N ms. 0 = never auto-reset. Default 8000. */
  resetAfterMs?: number
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }
  private resetTimer: number | null = null

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Send to console — production kiosk has no devtools but the
    // Chromium logs are reachable via `journalctl -u jarvis-dashboard`
    // when running under systemd.
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary caught an error:', error)
    // eslint-disable-next-line no-console
    console.error('Component stack:', info.componentStack)
  }

  componentDidUpdate(_prev: Props, prevState: State): void {
    // Schedule auto-reset only on the transition from no-error → error
    // (avoid resetting the timer on every render while the error persists).
    if (this.state.error && !prevState.error) {
      const ms = this.props.resetAfterMs ?? 8000
      if (ms > 0) {
        this.resetTimer = window.setTimeout(() => this.reset(), ms)
      }
    }
  }

  componentWillUnmount(): void {
    if (this.resetTimer !== null) {
      window.clearTimeout(this.resetTimer)
    }
  }

  private reset = (): void => {
    if (this.resetTimer !== null) {
      window.clearTimeout(this.resetTimer)
      this.resetTimer = null
    }
    this.setState({ error: null })
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children

    if (this.props.fallback) {
      return this.props.fallback(error, this.reset)
    }

    // Default fallback — match the dashboard's dark canvas so it
    // doesn't visually pop. Brief, focused on user action over detail.
    return (
      <div
        role="alert"
        style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 32,
          background: 'rgba(8, 12, 20, 0.92)',
          color: 'rgba(232, 232, 232, 0.92)',
          fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
          textAlign: 'center',
          zIndex: 9999,
        }}
      >
        <div style={{ fontSize: 28, fontWeight: 600, marginBottom: 12 }}>
          Something went wrong on the dashboard
        </div>
        <div style={{ fontSize: 14, opacity: 0.7, marginBottom: 24, maxWidth: 480 }}>
          The interface hit a render error and is recovering automatically.
          If this keeps happening, refresh the page.
        </div>
        <button
          onClick={this.reset}
          style={{
            padding: '10px 28px',
            borderRadius: 8,
            border: '1px solid rgba(232, 192, 112, 0.4)',
            background: 'rgba(232, 192, 112, 0.12)',
            color: 'rgba(232, 192, 112, 0.95)',
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          Retry now
        </button>
        {/* Show error message in a tiny mono block for self-debugging.
            Hidden in production via env check would be nicer but the
            kiosk runs the build directly — keep it visible, kept small. */}
        <pre
          style={{
            marginTop: 24,
            padding: 12,
            borderRadius: 6,
            background: 'rgba(0, 0, 0, 0.3)',
            color: 'rgba(232, 232, 232, 0.5)',
            fontSize: 11,
            fontFamily: 'JetBrains Mono, monospace',
            maxWidth: 600,
            overflow: 'auto',
          }}
        >
          {error.name}: {error.message}
        </pre>
      </div>
    )
  }
}
