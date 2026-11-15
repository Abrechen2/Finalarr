import { fireEvent, screen, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import type { EventView } from '../lib/events'
import type { SeriesDetail } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/render'
import { EventsPage } from './EventsPage'
import { SeriesDetailPage } from './SeriesDetailPage'

afterEach(() => vi.unstubAllGlobals())

const event: EventView = {
  id: 9,
  type: 'episodes_available',
  created_at: '2026-11-13T10:00:00Z',
  series_id: 1,
  season_id: 3,
  fingerprint: 'abc',
  payload: { title: 'Slime', season: 3, episodes: [5, 6, 7], have: 7, expected: 12 },
  deliveries: [
    {
      id: 1,
      channel_id: 1,
      channel_name: 'Telegram',
      status: 'sent',
      attempts: 1,
      last_error: null,
      sent_at: null,
    },
    {
      id: 2,
      channel_id: 2,
      channel_name: 'Discord',
      status: 'failed',
      attempts: 3,
      last_error: 'HTTP 401',
      sent_at: null,
    },
  ],
}

test('events show the message, a series link and delivery dots', async () => {
  mockFetch({ 'GET /api/v1/events': { body: { items: [event], next_cursor: null } } })
  renderWithProviders(<EventsPage />, { route: '/events' })
  const link = await screen.findByRole('link', { name: 'Slime S03 E05–E07 verfügbar (7/12)' })
  expect(link).toHaveAttribute('href', '/series/1')
  expect(screen.getByLabelText('Telegram: gesendet')).toBeInTheDocument()
  expect(screen.getByLabelText('Discord: fehlgeschlagen (HTTP 401)')).toBeInTheDocument()
})

test('type filter is sent to the API', async () => {
  const calls = mockFetch({
    'GET /api/v1/events': { body: { items: [], next_cursor: null } },
    'GET /api/v1/events?type=season_complete': { body: { items: [], next_cursor: null } },
  })
  renderWithProviders(<EventsPage />, { route: '/events' })
  expect(await screen.findByText('Noch keine Ereignisse')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'season_complete' } })
  expect(await screen.findByText('Keine Ereignisse zu diesem Filter.')).toBeInTheDocument()
  expect(calls.map((c) => c.url)).toContain('/api/v1/events?type=season_complete')
})

test('pagination and undelivered events', async () => {
  mockFetch({
    'GET /api/v1/events': { body: { items: [{ ...event, deliveries: [] }], next_cursor: '9' } },
    'GET /api/v1/events?cursor=9': {
      body: { items: [{ ...event, id: 8, series_id: null, deliveries: [] }], next_cursor: null },
    },
  })
  renderWithProviders(<EventsPage />, { route: '/events' })
  expect(await screen.findByText('noch an keinen Kanal zugestellt')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Mehr laden' }))
  await waitFor(() =>
    expect(screen.getAllByText('noch an keinen Kanal zugestellt')).toHaveLength(2),
  )
})

test('event errors are shown', async () => {
  mockFetch({ 'GET /api/v1/events': { status: 500, body: {} } })
  renderWithProviders(<EventsPage />, { route: '/events' })
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

const detail = {
  id: 1,
  instance_id: 1,
  title: 'Slime',
  year: null,
  series_type: 'anime',
  status: '',
  poster_url: null,
  monitored: true,
  followed: true,
  include_specials: false,
  respect_monitoring: true,
  calendar: true,
  anilist_id: null,
  anilist_resolution: 'none',
  tags: [],
  sonarr_url: 'x',
  seasons: [
    {
      id: 3,
      number: 3,
      state: 'airing',
      expected: 12,
      have: 7,
      disputed: false,
      expected_source: 'sonarr',
      expected_override: null,
      anilist_count: null,
      parts_mode: 'season',
      anilist_ids: [],
      anilist_pinned: false,
      anilist_start: null,
      monitored: true,
      state_since: null,
      parts: [],
      episodes: [],
    },
  ],
} as SeriesDetail

function renderDetail() {
  renderWithProviders(
    <Routes>
      <Route path="/series/:id" element={<SeriesDetailPage />} />
    </Routes>,
    { route: '/series/1' },
  )
}

test('check now lists the would-be events', async () => {
  mockFetch({
    'GET /api/v1/series/1': { body: detail },
    'POST /api/v1/seasons/3/evaluate?dry_run=true': {
      body: {
        state: 'airing',
        events: [{ type: 'season_complete', payload: { season: 3, have: 12, expected: 12 } }],
      },
    },
  })
  renderDetail()
  fireEvent.click(await screen.findByRole('button', { name: 'Einstellungen für Staffel 3' }))
  fireEvent.click(screen.getByRole('button', { name: 'Jetzt prüfen' }))
  expect(await screen.findByText('Slime Staffel 3 komplett (12/12)')).toBeInTheDocument()
})

test('check now with nothing due, and reload from Sonarr', async () => {
  mockFetch({
    'GET /api/v1/series/1': { body: detail },
    'POST /api/v1/seasons/3/evaluate?dry_run=true': { body: { state: 'airing', events: [] } },
    'POST /api/v1/seasons/3/evaluate': { status: 202, body: { queued: true } },
  })
  renderDetail()
  fireEvent.click(await screen.findByRole('button', { name: 'Einstellungen für Staffel 3' }))
  fireEvent.click(screen.getByRole('button', { name: 'Jetzt prüfen' }))
  expect(await screen.findByText('Keine neue Meldung fällig. Zustand: läuft.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Von Sonarr neu laden' }))
  expect(await screen.findByText('Abgleich mit Sonarr ist angestoßen.')).toBeInTheDocument()
})

test('check errors are shown', async () => {
  mockFetch({
    'GET /api/v1/series/1': { body: detail },
    'POST /api/v1/seasons/3/evaluate?dry_run=true': { status: 500, body: {} },
  })
  renderDetail()
  fireEvent.click(await screen.findByRole('button', { name: 'Einstellungen für Staffel 3' }))
  fireEvent.click(screen.getByRole('button', { name: 'Jetzt prüfen' }))
  expect(await screen.findByText(/Etwas ist schiefgelaufen/)).toBeInTheDocument()
})

test('series rule switches patch the series', async () => {
  const calls = mockFetch({
    'GET /api/v1/series/1': { body: detail },
    'PATCH /api/v1/series/1': { body: { ...detail, include_specials: true } },
  })
  renderDetail()
  fireEvent.click(await screen.findByLabelText('Specials (Staffel 0) einbeziehen'))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'PATCH')).toBe(true))
  expect(JSON.parse(String(calls.find((c) => c.init?.method === 'PATCH')?.init?.body))).toEqual({
    include_specials: true,
  })
})

test('resend queues the event again', async () => {
  const calls = mockFetch({
    'GET /api/v1/events': { body: { items: [event], next_cursor: null } },
    'POST /api/v1/events/9/resend': { status: 202, body: { queued: 2 } },
  })
  renderWithProviders(<EventsPage />, { route: '/events' })
  fireEvent.click(await screen.findByRole('button', { name: 'Erneut senden' }))
  expect(await screen.findByText('Wird erneut gesendet.')).toBeInTheDocument()
  expect(calls.some((c) => c.url === '/api/v1/events/9/resend')).toBe(true)
})

test('news hints link to the article', async () => {
  mockFetch({
    'GET /api/v1/events': {
      body: {
        items: [
          {
            ...event,
            type: 'news_mention',
            payload: {
              title: 'Slime',
              headline: 'S4 Part 3',
              link: 'https://www.livechart.me/headlines/1',
            },
            deliveries: [],
          },
        ],
        next_cursor: null,
      },
    },
  })
  renderWithProviders(<EventsPage />, { route: '/events' })
  expect(await screen.findByRole('link', { name: 'livechart.me' })).toHaveAttribute(
    'href',
    'https://www.livechart.me/headlines/1',
  )
})
