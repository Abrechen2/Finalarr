import { screen } from '@testing-library/react'
import App from './App'
import { mockFetch, renderWithProviders } from './test/render'

afterEach(() => vi.unstubAllGlobals())

test('an anonymous visitor is sent to the login page', async () => {
  mockFetch({ 'GET /api/v1/auth/status': { body: { authenticated: false } } })
  renderWithProviders(<App />, { route: '/series' })
  expect(await screen.findByLabelText('API-Schlüssel')).toBeInTheDocument()
})

test('a signed-in user sees the page inside the shell', async () => {
  mockFetch({
    'GET /api/v1/auth/status': { body: { authenticated: true } },
    'GET /api/v1/series': { body: { items: [], next_cursor: null } },
  })
  renderWithProviders(<App />, { route: '/series' })
  expect(await screen.findByRole('heading', { name: 'Serien' })).toBeInTheDocument()
  expect(await screen.findByText('Keine Serien')).toBeInTheDocument()
})

test('the about page shows the running version', async () => {
  mockFetch({
    'GET /api/v1/auth/status': { body: { authenticated: true } },
    'GET /health': { body: { status: 'ok', version: '0.0.1' } },
  })
  renderWithProviders(<App />, { route: '/about' })
  expect(await screen.findByText('0.0.1')).toBeInTheDocument()
})
