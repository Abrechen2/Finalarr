import { screen } from '@testing-library/react'
import i18n from '../i18n'
import { mockFetch, renderWithProviders } from '../test/render'
import { OnboardingPage } from './OnboardingPage'

afterEach(() => vi.unstubAllGlobals())
beforeEach(() => i18n.changeLanguage('de'))

const instance = {
  id: 1,
  name: 'Home',
  url: 'http://sonarr:8989',
  api_key: '••••',
  enabled: true,
  webhook_path: '/webhook/sonarr/abc',
}

test('setup shows that the first sync runs and the webhook is still missing', async () => {
  mockFetch({
    'GET /api/v1/instances': {
      body: [{ ...instance, last_sync_at: null, last_webhook_at: null, last_error: null }],
    },
  })
  renderWithProviders(<OnboardingPage />)
  expect(await screen.findByText('Erster Abgleich mit Sonarr läuft …')).toBeInTheDocument()
  expect(screen.getByText(/Noch kein Webhook angekommen/)).toBeInTheDocument()
})

test('setup confirms sync and webhook, or shows the sync error', async () => {
  mockFetch({
    'GET /api/v1/instances': {
      body: [
        {
          ...instance,
          last_sync_at: '2026-11-14T15:00:00Z',
          last_webhook_at: '2026-11-14T15:01:00Z',
          last_error: null,
        },
      ],
    },
  })
  renderWithProviders(<OnboardingPage />)
  expect(await screen.findByText(/Abgleich mit Sonarr fertig/)).toHaveClass('text-ok')
  expect(screen.getByText(/Webhook von Sonarr angekommen/)).toHaveClass('text-ok')
})

test('a failed sync is shown in red', async () => {
  mockFetch({
    'GET /api/v1/instances': {
      body: [{ ...instance, last_sync_at: null, last_webhook_at: null, last_error: 'HTTP 401' }],
    },
  })
  renderWithProviders(<OnboardingPage />)
  expect(await screen.findByText('Abgleich mit Sonarr fehlgeschlagen: HTTP 401')).toHaveClass(
    'text-bad',
  )
})
