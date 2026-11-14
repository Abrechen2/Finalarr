import { fireEvent, screen, waitFor } from '@testing-library/react'
import i18n from '../i18n'
import { WatchPanel } from '../components/WatchPanel'
import { EpisodeGrid } from '../components/EpisodeGrid'
import type { SeriesDetail } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/render'
import { MediaServersSettings } from './MediaServersSettings'

afterEach(() => vi.unstubAllGlobals())
beforeEach(() => i18n.changeLanguage('de'))

const series = {
  id: 5,
  title: 'Slime',
  followed: true,
  follow_mode: 'auto',
  watch: {
    enabled: true,
    users: [
      { name: 'Dennis', server: 'Plex', watched: 2, last_watched: '2026-11-08' },
      { name: 'Anna', server: 'Plex', watched: 1, last_watched: null },
    ],
    episodes: { '1x1': ['Dennis', 'Anna'] },
    unwatched_on_disk: 1,
    next_unwatched: { season: 1, episode: 3 },
  },
} as unknown as SeriesDetail

test('watch panel shows who watched what and switches the follow mode', async () => {
  const calls = mockFetch({
    'PATCH /api/v1/series/5': { body: { ...series, follow_mode: 'never' } },
  })
  renderWithProviders(<WatchPanel series={series} />)
  expect(screen.getByText(/Dennis: 2 Folgen, zuletzt/)).toBeInTheDocument()
  expect(screen.getByText('Anna: 1 Folgen')).toBeInTheDocument()
  expect(
    screen.getByText('1 Folge auf der Platte ist noch ungesehen, als Nächstes S01E03.'),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Automatisch' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Nie' }))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({ followed: false })
})

test('watch panel hands a series back to automatic and hides without servers', async () => {
  const always = { ...series, follow_mode: 'always' } as SeriesDetail
  const calls = mockFetch({ 'PATCH /api/v1/series/5': { body: series } })
  const { unmount } = renderWithProviders(<WatchPanel series={always} />)
  fireEvent.click(screen.getByRole('button', { name: 'Automatisch' }))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({ follow_mode: 'auto' })
  unmount()
  const off = { ...series, watch: { ...series.watch, enabled: false } } as SeriesDetail
  const { container } = renderWithProviders(<WatchPanel series={off} />)
  expect(container).toBeEmptyDOMElement()
})

test('watched episodes are marked in the grid', () => {
  renderWithProviders(
    <EpisodeGrid
      season={1}
      now={new Date('2026-11-14T00:00:00Z')}
      watched={{ '1x1': ['Dennis', 'Anna'] }}
      episodes={[1, 2].map((n) => ({
        id: n,
        number: n,
        absolute_number: null,
        title: `Ep ${n}`,
        air_date: '2026-10-01T15:00:00Z',
        monitored: true,
        has_file: true,
        finale_type: null,
      }))}
    />,
  )
  expect(screen.getByLabelText(/S01E01: .*gesehen von Dennis, Anna/)).toBeInTheDocument()
  expect(screen.getByLabelText('S01E02: vorhanden')).toBeInTheDocument()
})

const server = {
  id: 1,
  kind: 'plex',
  name: 'Plex',
  url: 'http://plex:32400',
  token: '***abcd',
  enabled: true,
  version: null,
  last_sync_at: null,
  last_error: null,
  unmatched: ['Severance'],
  users: [
    { id: 7, name: 'Dennis', selected: true, watched_episodes: 42 },
    { id: 8, name: 'Kids', selected: false, watched_episodes: 0 },
  ],
}

test('media server settings: users, unmatched series, add with connection test', async () => {
  const calls = mockFetch({
    'GET /api/v1/media-servers': { body: [server] },
    'GET /api/v1/settings': {
      body: { auto_follow: true, auto_follow_min_episodes: 2, auto_follow_days: 30 },
    },
    'PATCH /api/v1/media-servers/1/users/8': { body: { id: 8, name: 'Kids', selected: true } },
    'POST /api/v1/media-servers/test': { body: { version: 'Home Emby 4.9' } },
  })
  renderWithProviders(<MediaServersSettings />)
  expect(await screen.findByText('42 Folgen gesehen')).toBeInTheDocument()
  expect(
    screen.getByText('1 gesehene Serie ist keiner Sonarr-Serie zugeordnet'),
  ).toBeInTheDocument()
  expect(screen.getByText('Noch nicht abgeglichen')).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('Kids'))
  await waitFor(() =>
    expect(calls.some((c) => c.url === '/api/v1/media-servers/1/users/8')).toBe(true),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Mediaserver hinzufügen' }))
  fireEvent.change(screen.getByLabelText('Adresse'), { target: { value: 'http://emby:8096' } })
  fireEvent.change(screen.getByLabelText(/API-Schlüssel/), { target: { value: 'k' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verbindung testen' }))
  expect(await screen.findByText('Verbunden: Home Emby 4.9')).toBeInTheDocument()
  const test = calls.find((c) => c.url === '/api/v1/media-servers/test')
  expect(JSON.parse(String(test?.init?.body))).toEqual({
    kind: 'emby',
    name: 'Emby',
    url: 'http://emby:8096',
    token: 'k',
  })
  expect(await screen.findByLabelText('Serien folgen, die jemand schaut')).toBeChecked()
})

test('a rejected token is explained', async () => {
  mockFetch({
    'GET /api/v1/media-servers': { body: [] },
    'GET /api/v1/settings': {
      body: { auto_follow: true, auto_follow_min_episodes: 2, auto_follow_days: 30 },
    },
    'POST /api/v1/media-servers/test': {
      status: 502,
      body: { error: { code: 'media_unreachable', message: 'Plex rejected the token' } },
    },
  })
  renderWithProviders(<MediaServersSettings />)
  expect(await screen.findByText('Noch kein Mediaserver verbunden.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Mediaserver hinzufügen' }))
  fireEvent.change(screen.getByLabelText('Adresse'), { target: { value: 'http://plex:32400' } })
  fireEvent.change(screen.getByLabelText(/API-Schlüssel/), { target: { value: 'x' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verbindung testen' }))
  expect(
    await screen.findByText(
      'Mediaserver nicht erreichbar oder Schlüssel abgelehnt: Plex rejected the token',
    ),
  ).toBeInTheDocument()
})
