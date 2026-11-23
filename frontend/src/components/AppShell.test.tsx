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
  for (const label of ['Übersicht', 'Serien', 'Gesehen', 'Ereignisse', 'Einstellungen', 'Über']) {
    expect(nav).toHaveTextContent(label)
  }
  expect(screen.getByRole('link', { name: 'Serien' })).toHaveAttribute('aria-current', 'page')
  // Phones reach About from the header; the bottom bar has no room for it.
  expect(screen.getAllByRole('link', { name: 'Über' })).toHaveLength(2)
  expect(screen.getByText('Inhalt')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Ein Projekt von/ })).toBeInTheDocument()
})
