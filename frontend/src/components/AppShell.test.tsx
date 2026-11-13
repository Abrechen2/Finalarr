import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test/render'
import { AppShell } from './AppShell'

test('shows the German navigation, the credit and the page content', () => {
  renderWithProviders(
    <AppShell>
      <p>Inhalt</p>
    </AppShell>,
    { route: '/series' },
  )
  const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
  for (const label of ['Übersicht', 'Serien', 'Ereignisse', 'Einstellungen', 'Über']) {
    expect(nav).toHaveTextContent(label)
  }
  expect(screen.getByRole('link', { name: 'Serien' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByText('Inhalt')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Ein Projekt von/ })).toBeInTheDocument()
})
