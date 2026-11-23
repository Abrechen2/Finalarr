import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from './EmptyState'

function Crashed() {
  const { t } = useTranslation()
  return (
    <div role="alert">
      <EmptyState title={t('page.crashTitle')}>{t('page.crash')}</EmptyState>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="mt-4 rounded-control bg-accent px-3 py-1.5 text-sm font-bold text-on-accent"
      >
        {t('page.reload')}
      </button>
    </div>
  )
}

/** Keeps a crashing page from blanking the whole app; the navigation stays usable.
 * Give it a ``key`` per route so switching pages recovers. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page crashed', error, info.componentStack)
  }

  render() {
    return this.state.failed ? <Crashed /> : this.props.children
  }
}
