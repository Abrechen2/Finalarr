import { fireEvent, screen, waitFor } from '@testing-library/react'
import i18n from '../i18n'
import { mockFetch, renderWithProviders } from '../test/render'
import { WatchTrackerPage } from './WatchTrackerPage'

afterEach(() => vi.unstubAllGlobals())
beforeEach(() => i18n.changeLanguage('de'))

const stats = {
  episodes: 120,
  minutes: 2880,
  undated: 80,
  this_week: 5,
  this_month: 21,
  weekly: [
    { week: '2026-11-09', episodes: 4 },
    { week: '2026-11-16', episodes: 12 },
    { week: '2026-11-23', episodes: 5 },
  ],
  series: { started: 9, behind: 3, abandoned: 1, caught_up: 2, finished: 1, unknown: 3 },
  users: [
    { id: 1, name: 'Anna', server: 'Emby' },
    { id: 2, name: 'Dennis', server: 'Emby' },
  ],
}

const rows = [
  {
    series_id: 7,
    title: 'Slime',
    poster_url: null,
    state: 'behind',
    watched: 22,
    unwatched: 3,
    next: { season: 2, episode: 4 },
    last_watched: '2026-11-24',
  },
  {
    series_id: 8,
    title: 'Andor',
    poster_url: null,
    state: 'finished',
    watched: 24,
    unwatched: 0,
    next: null,
    last_watched: '2026-11-10',
  },
]

test('shows stats, the weekly chart and what is still missing', async () => {
  mockFetch({
    'GET /api/v1/watch/stats': { body: stats },
    'GET /api/v1/watch/series?state=all&sort=recent': { body: rows },
  })
  renderWithProviders(<WatchTrackerPage />)
  expect(await screen.findByText('120')).toBeInTheDocument()
  expect(screen.getByText('48 Stunden')).toBeInTheDocument()
  expect(screen.getByText(/80 Folgen aus der ersten Synchronisierung/)).toBeInTheDocument()
  // Each bar names its week and count for screen readers and on hover.
  expect(screen.getByRole('img', { name: /Woche ab 16\.11\.: 12 Folgen/ })).toBeInTheDocument()
  expect(await screen.findByRole('link', { name: 'Slime' })).toHaveAttribute('href', '/series/7')
  expect(screen.getByText('3 ungesehen · als Nächstes S02E04')).toBeInTheDocument()
  expect(screen.getByText('Fertig geschaut')).toBeInTheDocument()
})

test('filters, sorts and switches the user', async () => {
  const calls = mockFetch({
    'GET /api/v1/watch/stats': { body: stats },
    'GET /api/v1/watch/series?state=all&sort=recent': { body: rows },
    'GET /api/v1/watch/series?state=behind&sort=recent': { body: [rows[0]] },
    'GET /api/v1/watch/series?state=behind&sort=open': { body: [rows[0]] },
    'GET /api/v1/watch/stats?user=2': { body: stats },
    'GET /api/v1/watch/series?state=behind&sort=open&user=2': { body: [] },
  })
  renderWithProviders(<WatchTrackerPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Hinterher (3)' }))
  await waitFor(() => expect(screen.queryByRole('link', { name: 'Andor' })).toBeNull())
  fireEvent.change(screen.getByRole('combobox', { name: 'Sortierung' }), {
    target: { value: 'open' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Wer' }), { target: { value: '2' } })
  expect(await screen.findByText('Nichts in dieser Auswahl.')).toBeInTheDocument()
  expect(calls.map((c) => c.url)).toContain('/api/v1/watch/stats?user=2')
})

test('without a media server it points to the settings', async () => {
  mockFetch({
    'GET /api/v1/watch/stats': { body: { ...stats, users: [], episodes: 0 } },
    'GET /api/v1/watch/series?state=all&sort=recent': { body: [] },
  })
  renderWithProviders(<WatchTrackerPage />)
  expect(await screen.findByText(/Verbinde Emby, Jellyfin oder Plex/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Einstellungen' })).toHaveAttribute('href', '/settings')
})
