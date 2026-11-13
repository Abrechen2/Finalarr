import { fireEvent, screen, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { mockFetch, renderWithProviders } from '../test/render'
import { LoginPage } from './LoginPage'

afterEach(() => vi.unstubAllGlobals())

function renderLogin() {
  renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<p>Startseite</p>} />
    </Routes>,
    { route: '/login' },
  )
}

test('a correct key logs in and goes to the overview', async () => {
  const calls = mockFetch({ 'POST /api/v1/auth/login': { body: { authenticated: true } } })
  renderLogin()
  fireEvent.change(screen.getByLabelText('API-Schlüssel'), { target: { value: 'secret-key' } })
  fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))
  expect(await screen.findByText('Startseite')).toBeInTheDocument()
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({ api_key: 'secret-key' })
})

test('a wrong key shows a friendly German error', async () => {
  mockFetch({
    'POST /api/v1/auth/login': {
      status: 401,
      body: { error: { code: 'unauthorized', message: 'Invalid API key' } },
    },
  })
  renderLogin()
  fireEvent.change(screen.getByLabelText('API-Schlüssel'), { target: { value: 'x' } })
  fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Schlüssel ist falsch'))
})

test('too many attempts get their own message', async () => {
  mockFetch({
    'POST /api/v1/auth/login': {
      status: 429,
      body: { error: { code: 'rate_limited', message: 'Too many' } },
    },
  })
  renderLogin()
  fireEvent.change(screen.getByLabelText('API-Schlüssel'), { target: { value: 'x' } })
  fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Zu viele Versuche'))
})
