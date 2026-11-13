import { fireEvent, screen, waitFor } from '@testing-library/react'
import type { SeasonDetail } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/render'
import { AnilistPicker } from './AnilistPicker'
import { SeasonParts } from './SeasonParts'

afterEach(() => vi.unstubAllGlobals())

const season: SeasonDetail = {
  id: 7,
  number: 2,
  state: 'airing',
  expected: 25,
  have: 13,
  disputed: false,
  expected_source: 'sonarr',
  expected_override: null,
  anilist_count: 25,
  parts_mode: 'season',
  anilist_ids: [146065, 166873],
  anilist_pinned: false,
  anilist_start: null,
  monitored: true,
  state_since: null,
  episodes: [],
  parts: [
    { index: 1, from: 1, to: 13, title: 'Mushoku II' },
    { index: 2, from: 14, to: 25, title: 'Mushoku II Part 2' },
  ],
}
const candidates = [
  {
    id: 146065,
    title: 'Mushoku II',
    romaji: null,
    format: 'TV',
    status: 'FINISHED',
    episodes: 13,
    start_date: '2023-07-03',
  },
  {
    id: 999,
    title: 'Other',
    romaji: null,
    format: 'MOVIE',
    status: 'FINISHED',
    episodes: 1,
    start_date: null,
  },
]

test('shows the automatic mapping and pins a new choice', async () => {
  const calls = mockFetch({
    'GET /api/v1/anilist/search?q=Mushoku': { body: candidates },
    'PUT /api/v1/seasons/7/anilist': { body: {} },
  })
  renderWithProviders(<AnilistPicker seriesId={1} seriesTitle="Mushoku" season={season} />)
  expect(screen.getByText('AniList: #146065, #166873 (automatisch)')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'AniList zuordnen' }))
  fireEvent.click(screen.getByRole('button', { name: 'Suchen' }))
  const other = await screen.findByRole('checkbox', { name: /Other/ })
  expect(screen.getByText('TV · 2023 · 13 Folgen')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: /Mushoku II/ }))
  fireEvent.click(other)
  fireEvent.click(screen.getByRole('button', { name: 'Zuordnung speichern' }))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'PUT')).toBe(true))
  expect(JSON.parse(String(calls.find((c) => c.init?.method === 'PUT')?.init?.body))).toEqual({
    anilist_ids: [166873, 999],
  })
})

test('manual mapping can be removed; AniList outage is explained', async () => {
  const calls = mockFetch({
    'GET /api/v1/anilist/search?q=Mushoku': {
      status: 503,
      body: { error: { code: 'anilist_unavailable', message: 'x' } },
    },
    'PUT /api/v1/seasons/7/anilist': { status: 202, body: { saved: true, enriched: false } },
  })
  renderWithProviders(
    <AnilistPicker
      seriesId={1}
      seriesTitle="Mushoku"
      season={{ ...season, anilist_pinned: true, anilist_ids: [] }}
    />,
  )
  expect(screen.getByText('Keine AniList-Zuordnung.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Manuelle Zuordnung entfernen' }))
  expect(await screen.findByText(/AniList wird beim nächsten Lauf abgefragt/)).toBeInTheDocument()
  expect(JSON.parse(String(calls.at(-1)?.init?.body))).toEqual({ anilist_ids: [] })
  fireEvent.click(screen.getByRole('button', { name: 'AniList zuordnen' }))
  fireEvent.click(screen.getByRole('button', { name: 'Suchen' }))
  expect(await screen.findByText(/AniList ist gerade nicht erreichbar/)).toBeInTheDocument()
})

test('parts are listed and the parts mode toggles', async () => {
  const calls = mockFetch({ 'PATCH /api/v1/seasons/7': { body: {} } })
  renderWithProviders(<SeasonParts seriesId={1} season={season} />)
  expect(screen.getByText('Teil 2: Folgen 14–25')).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText(/Teile als eigene Staffeln melden/))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({ parts_mode: 'parts' })
})

test('a season without split cours shows no parts block', () => {
  const { container } = renderWithProviders(
    <SeasonParts seriesId={1} season={{ ...season, parts: [] }} />,
  )
  expect(container).toBeEmptyDOMElement()
})
