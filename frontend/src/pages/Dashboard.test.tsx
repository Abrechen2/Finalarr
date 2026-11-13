import { fireEvent, screen, waitFor } from '@testing-library/react'
import { mockFetch, renderWithProviders } from '../test/render'
import type { Dashboard } from './DashboardPage'
import { DashboardPage } from './DashboardPage'
import { OnboardingPage } from './OnboardingPage'

afterEach(() => vi.unstubAllGlobals())

const empty: Dashboard = {
  airing: [],
  upcoming_finales: [],
  recent_events: [],
  onboarding: { instance: true, followed: false, channel: false },
}

test('a fresh install shows the setup checklist and empty columns', async () => {
  mockFetch({ 'GET /api/v1/dashboard': { body: empty } })
  renderWithProviders(<DashboardPage />)
  expect(await screen.findByText('Einrichtung')).toBeInTheDocument()
  expect(screen.getByLabelText('erledigt')).toBeInTheDocument()
  expect(screen.getAllByLabelText('offen')).toHaveLength(2)
  expect(screen.getByRole('link', { name: 'Einrichtung starten' })).toHaveAttribute(
    'href',
    '/onboarding',
  )
  expect(screen.getByText('Gerade läuft keine gefolgte Staffel.')).toBeInTheDocument()
  expect(screen.getByText('Kein Finale in Sicht.')).toBeInTheDocument()
})

test('airing seasons, finales and recent events', async () => {
  const card = {
    series_id: 1,
    season_id: 3,
    title: 'Slime',
    season: 3,
    state: 'airing' as const,
    have: 7,
    expected: 12,
    disputed: false,
    next_air_date: '2026-11-20T15:00:00Z',
  }
  mockFetch({
    'GET /api/v1/dashboard': {
      body: {
        airing: [card],
        upcoming_finales: [{ ...card, episode: 12, air_date: '2026-12-18T15:00:00Z' }],
        recent_events: [
          {
            id: 1,
            type: 'season_complete',
            created_at: '2026-11-13T10:00:00Z',
            series_id: 2,
            season_id: 4,
            fingerprint: 'f',
            deliveries: [],
            payload: { title: 'Andor', season: 2, have: 12, expected: 12 },
          },
        ],
        onboarding: { instance: true, followed: true, channel: true },
      },
    },
  })
  renderWithProviders(<DashboardPage />)
  expect(await screen.findByText('7/12')).toBeInTheDocument()
  expect(screen.queryByText('Einrichtung')).not.toBeInTheDocument()
  expect(screen.getByText(/nächste Folge 20\.11\.2026/)).toBeInTheDocument()
  expect(screen.getByText('S03E12 am 18.12.2026')).toBeInTheDocument()
  expect(screen.getByText('Andor Staffel 2 komplett (12/12)')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Erneut senden' })).not.toBeInTheDocument()
})

test('dashboard errors are shown', async () => {
  mockFetch({ 'GET /api/v1/dashboard': { status: 500, body: {} } })
  renderWithProviders(<DashboardPage />)
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

const instance = {
  id: 1,
  name: 'Sonarr',
  url: 'http://sonarr:8989',
  api_key: '***abcd',
  enabled: true,
  webhook_path: '/webhook/sonarr/' + 'a'.repeat(64),
  last_sync_at: null,
  last_error: null,
}

test('onboarding walks through Sonarr, following and a channel', async () => {
  const calls = mockFetch({
    'GET /api/v1/instances': { body: [] },
    'POST /api/v1/instances/test': { body: { ok: true, version: '4.0.15' } },
    'POST /api/v1/instances': { status: 201, body: instance },
    'GET /api/v1/series?followed=true&limit=200': { body: { items: [], next_cursor: null } },
    'POST /api/v1/series/follow-monitored': { body: { followed: 5 } },
  })
  renderWithProviders(<OnboardingPage />)
  expect(await screen.findByText('Schritt 1 von 3')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Weiter' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Sonarr-Adresse'), {
    target: { value: 'http://sonarr:8989' },
  })
  fireEvent.change(screen.getByLabelText('API-Schlüssel'), { target: { value: 'k' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verbindung testen' }))
  expect(await screen.findByText('Verbunden mit Sonarr 4.0.15.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  expect(await screen.findByText(/webhook\/sonarr\/a{64}/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Weiter' }))
  expect(await screen.findByText('Du folgst 0 Serien.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Alle überwachten folgen' }))
  await waitFor(() =>
    expect(calls.some((c) => c.url === '/api/v1/series/follow-monitored')).toBe(true),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Weiter' }))
  expect(await screen.findByText('Schritt 3 von 3')).toBeInTheDocument()
  expect(screen.getByLabelText('Bot-Token (von @BotFather)')).toBeInTheDocument()
})

test('onboarding errors from Sonarr are friendly', async () => {
  mockFetch({
    'GET /api/v1/instances': { body: [] },
    'POST /api/v1/instances/test': {
      status: 502,
      body: { error: { code: 'sonarr_auth', message: 'x' } },
    },
  })
  renderWithProviders(<OnboardingPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Verbindung testen' }))
  expect(await screen.findByText('Sonarr hat den API-Schlüssel abgelehnt.')).toBeInTheDocument()
})
