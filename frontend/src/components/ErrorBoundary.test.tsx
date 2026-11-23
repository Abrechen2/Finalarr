import { screen } from '@testing-library/react'
import i18n from '../i18n'
import { NotFoundPage } from '../pages/NotFoundPage'
import { renderWithProviders } from '../test/render'
import { ErrorBoundary } from './ErrorBoundary'

beforeEach(() => i18n.changeLanguage('de'))

function Broken(): never {
  throw new Error('render failed')
}

test('a crashing page shows a message instead of a blank app', () => {
  const quiet = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  renderWithProviders(
    <ErrorBoundary>
      <Broken />
    </ErrorBoundary>,
  )
  expect(screen.getByRole('alert')).toHaveTextContent('Diese Seite ist abgestürzt')
  expect(screen.getByRole('button', { name: 'Neu laden' })).toBeInTheDocument()
  quiet.mockRestore()
})

test('an unknown address links back to the overview', () => {
  renderWithProviders(<NotFoundPage />)
  expect(screen.getByText('Seite nicht gefunden')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Zur Übersicht' })).toHaveAttribute('href', '/')
})
