import { fireEvent, screen, waitFor } from '@testing-library/react'
import { mockFetch, renderWithProviders } from '../test/render'
import { InstancesSettings } from './InstancesSettings'
import { SystemSettings } from './SystemSettings'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const instance = {
  id: 1,
  name: 'Home',
  url: 'http://sonarr:8989',
  api_key: '***abcd',
  enabled: true,
  webhook_path: '/webhook/sonarr/tok',
  last_sync_at: '2026-11-13T10:00:00Z',
  last_error: 'Sonarr cannot be reached',
}

test('instance row: status, webhook URL, actions', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const writeText = vi.fn(async () => undefined)
  Object.assign(navigator, { clipboard: { writeText } })
  const calls = mockFetch({
    'GET /api/v1/instances': { body: [instance] },
    'POST /api/v1/instances/1/test': {
      status: 502,
      body: { error: { code: 'sonarr_unreachable', message: 'x' } },
    },
    'POST /api/v1/instances/1/sync': { status: 202, body: { queued: true } },
    'POST /api/v1/instances/1/rotate-token': { body: instance },
    'PATCH /api/v1/instances/1': { body: instance },
    'DELETE /api/v1/instances/1': { status: 204, body: {} },
  })
  renderWithProviders(<InstancesSettings />)
  expect(await screen.findByText('Home')).toBeInTheDocument()
  expect(screen.getByText('Sonarr cannot be reached')).toBeInTheDocument()
  expect(screen.getByText(/Letzter Abgleich/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Kopieren' }))
  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/webhook/sonarr/tok`),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Verbindung testen' }))
  expect(
    await screen.findByText('Sonarr ist unter dieser Adresse nicht erreichbar.'),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Jetzt abgleichen' }))
  expect(await screen.findByText('Abgleich angestoßen.')).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('aktiv'))
  fireEvent.click(screen.getByRole('button', { name: 'Webhook-Token erneuern' }))
  fireEvent.click(screen.getByRole('button', { name: 'Löschen' }))
  await waitFor(() =>
    expect(calls.map((c) => c.init?.method)).toEqual(expect.arrayContaining(['PATCH', 'DELETE'])),
  )
})

test('empty list and add form with field error', async () => {
  mockFetch({
    'GET /api/v1/instances': { body: [] },
    'POST /api/v1/instances': {
      status: 400,
      body: {
        error: {
          code: 'validation',
          message: 'x',
          fields: { url: 'Sonarr URL must start with http' },
        },
      },
    },
  })
  renderWithProviders(<InstancesSettings />)
  expect(await screen.findByText('Noch keine Sonarr-Instanz.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Instanz hinzufügen' }))
  fireEvent.change(screen.getByLabelText('Sonarr-Adresse'), { target: { value: 'ftp://x' } })
  fireEvent.change(screen.getByLabelText('API-Schlüssel'), { target: { value: 'k' } })
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Main' } })
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  expect(await screen.findByText('Sonarr URL must start with http')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
  expect(screen.queryByLabelText('Sonarr-Adresse')).not.toBeInTheDocument()
})

test('system tab shows version, jobs and logs', async () => {
  mockFetch({
    'GET /api/v1/system/status': {
      body: {
        version: '0.3.0',
        db: 'ok',
        scheduler: {
          running: true,
          jobs: [
            { id: 'drain', next_run: '2026-11-13T10:00:05Z' },
            { id: 'x', next_run: null },
          ],
        },
        instances: [],
      },
    },
    'GET /api/v1/system/logs?tail=200': { body: { lines: ['line one', 'line two'] } },
  })
  renderWithProviders(<SystemSettings />)
  expect(await screen.findByText('0.3.0')).toBeInTheDocument()
  expect(screen.getByText('läuft')).toBeInTheDocument()
  expect(screen.getByText('drain')).toBeInTheDocument()
  expect(await screen.findByText(/line one/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Neu laden' }))
})

test('system errors are shown', async () => {
  mockFetch({ 'GET /api/v1/system/status': { status: 500, body: {} } })
  renderWithProviders(<SystemSettings />)
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})
