import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import type { SeriesDetail, SeriesSummary } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/render'
import { SeriesDetailPage } from './SeriesDetailPage'
import { SeriesPage } from './SeriesPage'

afterEach(() => vi.unstubAllGlobals())

const slime: SeriesSummary = {
  id: 1,
  instance_id: 1,
  title: 'Slime',
  year: 2018,
  series_type: 'anime',
  status: 'continuing',
  poster_url: null,
  monitored: true,
  followed: true,
  include_specials: false,
  respect_monitoring: true,
  calendar: true,
  anilist_id: null,
  anilist_resolution: 'none',
  tags: [],
  seasons: [{ id: 3, number: 3, state: 'airing', expected: 24, have: 7, disputed: false }],
}
const andor: SeriesSummary = {
  ...slime,
  id: 2,
  title: 'Andor',
  series_type: 'standard',
  followed: false,
  seasons: [],
}

test('lists series with progress for followed ones', async () => {
  mockFetch({ 'GET /api/v1/series': { body: { items: [andor, slime], next_cursor: null } } })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  const rows = await screen.findAllByRole('listitem')
  expect(within(rows[0]).getByText('Andor')).toBeInTheDocument()
  expect(within(rows[1]).getByText('7/24')).toBeInTheDocument()
  expect(within(rows[1]).getByText('2018 · Anime')).toBeInTheDocument()
})

test('filters go into the request', async () => {
  const calls = mockFetch({
    'GET /api/v1/series': { body: { items: [andor, slime], next_cursor: null } },
    'GET /api/v1/series?followed=true': { body: { items: [slime], next_cursor: null } },
  })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  await screen.findByText('Andor')
  fireEvent.click(screen.getByRole('button', { name: 'Gefolgt' }))
  await waitFor(() => expect(screen.queryByText('Andor')).not.toBeInTheDocument())
  expect(calls.map((c) => c.url)).toContain('/api/v1/series?followed=true')
})

test('follow toggle patches the series', async () => {
  const calls = mockFetch({
    'GET /api/v1/series': { body: { items: [andor], next_cursor: null } },
    'PATCH /api/v1/series/2': { body: { ...andor, followed: true, sonarr_url: 'x', seasons: [] } },
  })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  fireEvent.click(await screen.findByRole('button', { name: 'Folgen' }))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'PATCH')).toBe(true))
  const patch = calls.find((c) => c.init?.method === 'PATCH')
  expect(JSON.parse(String(patch?.init?.body))).toEqual({ followed: true })
})

test('load more fetches the next page', async () => {
  mockFetch({
    'GET /api/v1/series': { body: { items: [andor], next_cursor: 'abc' } },
    'GET /api/v1/series?cursor=abc': { body: { items: [slime], next_cursor: null } },
  })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  fireEvent.click(await screen.findByRole('button', { name: 'Mehr laden' }))
  expect(await screen.findByText('Slime')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Mehr laden' })).not.toBeInTheDocument()
})

test('follow all monitored reports how many were added', async () => {
  mockFetch({
    'GET /api/v1/series': { body: { items: [], next_cursor: null } },
    'POST /api/v1/series/follow-monitored': { body: { followed: 12 } },
  })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  expect(await screen.findByText('Keine Serien')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Alle überwachten folgen' }))
  expect(await screen.findByRole('status')).toHaveTextContent('12 Serien neu gefolgt')
})

test('an empty filter result says so', async () => {
  mockFetch({ 'GET /api/v1/series?q=zz': { body: { items: [], next_cursor: null } } })
  renderWithProviders(<SeriesPage />, { route: '/series?q=zz' })
  expect(await screen.findByText('Keine Serie passt zu diesem Filter.')).toBeInTheDocument()
})

test('list errors are shown', async () => {
  mockFetch({ 'GET /api/v1/series': { status: 500, body: { error: { code: 'x', message: 'y' } } } })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  expect(await screen.findByRole('alert')).toHaveTextContent('Etwas ist schiefgelaufen')
})

const detail: SeriesDetail = {
  ...slime,
  sonarr_url: 'http://sonarr:8989/series/slime',
  seasons: [
    {
      id: 3,
      number: 3,
      state: 'aired',
      expected: 24,
      have: 1,
      disputed: true,
      expected_source: 'anilist',
      expected_override: null,
      anilist_count: 24,
      parts_mode: 'season',
      anilist_ids: [],
      anilist_pinned: false,
      anilist_start: null,
      monitored: true,
      state_since: null,
      parts: [],
      episodes: [
        {
          id: 1,
          number: 1,
          absolute_number: null,
          title: 'E1',
          air_date: '2024-01-01T00:00:00Z',
          monitored: true,
          has_file: true,
          finale_type: null,
        },
      ],
    },
    {
      ...{ id: 4, number: 4, state: 'unknown', expected: null, have: 0, disputed: false },
      expected_source: null,
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
}

function renderDetail() {
  renderWithProviders(
    <Routes>
      <Route path="/series/:id" element={<SeriesDetailPage />} />
    </Routes>,
    { route: '/series/1' },
  )
}

test('detail shows seasons, dispute, unknown season hint and the Sonarr link', async () => {
  mockFetch({ 'GET /api/v1/series/1': { body: detail } })
  renderDetail()
  expect(await screen.findByRole('heading', { name: 'Slime' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'In Sonarr öffnen' })).toHaveAttribute(
    'href',
    detail.sonarr_url,
  )
  expect(screen.getByText('24 Folgen erwartet (Quelle: AniList)')).toBeInTheDocument()
  expect(screen.getByRole('note')).toHaveTextContent('Sonarr listet 1 Folgen, AniList nennt 24')
  expect(screen.getByText('Sonarr kennt diese Staffel noch nicht.')).toBeInTheDocument()
  const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
  expect(headings).toEqual(['News', 'Staffel 4', 'Staffel 3'])
})

test('detail of an unfollowed series explains why nothing happens', async () => {
  mockFetch({ 'GET /api/v1/series/1': { body: { ...detail, followed: false } } })
  renderDetail()
  expect(await screen.findByRole('button', { name: 'Folgen' })).toBeInTheDocument()
  expect(screen.getAllByText(/Du folgst dieser Serie nicht/)[0]).toBeInTheDocument()
})

test('detail 404 shows an error', async () => {
  mockFetch({
    'GET /api/v1/series/1': { status: 404, body: { error: { code: 'not_found', message: 'x' } } },
  })
  renderDetail()
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

test('follow all with a Sonarr tag', async () => {
  const calls = mockFetch({
    'GET /api/v1/series': { body: { items: [], next_cursor: null } },
    'GET /api/v1/series/tags': { body: ['anime', 'kids'] },
    'POST /api/v1/series/follow-monitored': { body: { followed: 3 } },
  })
  renderWithProviders(<SeriesPage />, { route: '/series' })
  fireEvent.change(await screen.findByLabelText('Sonarr-Tag'), { target: { value: 'anime' } })
  fireEvent.click(screen.getByRole('button', { name: 'Alle mit Tag folgen' }))
  expect(await screen.findByRole('status')).toHaveTextContent('3 Serien neu gefolgt')
  const post = calls.find((c) => c.init?.method === 'POST')
  expect(JSON.parse(String(post?.init?.body))).toEqual({ tag: 'anime' })
})
