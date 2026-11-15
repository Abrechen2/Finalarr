import { fireEvent, screen, waitFor } from '@testing-library/react'
import type { SeasonDetail } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/render'
import { SeasonOverride } from './SeasonOverride'

afterEach(() => vi.unstubAllGlobals())

const season: SeasonDetail = {
  id: 3,
  number: 1,
  state: 'airing',
  expected: 24,
  have: 12,
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
  episodes: Array.from({ length: 12 }, (_, i) => ({
    id: i,
    number: i + 1,
    absolute_number: null,
    title: '',
    air_date: null,
    monitored: true,
    has_file: true,
    finale_type: null,
  })),
}

function body(calls: { init?: RequestInit }[]) {
  return JSON.parse(String(calls.at(-1)?.init?.body))
}

test('typing a number and saving sends the override', async () => {
  const calls = mockFetch({ 'PATCH /api/v1/seasons/3': { body: {} } })
  renderWithProviders(<SeasonOverride seriesId={1} season={season} />)
  fireEvent.change(screen.getByLabelText('Folgenzahl selbst festlegen'), {
    target: { value: '13' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  expect(await screen.findByText('Gespeichert.')).toBeInTheDocument()
  expect(body(calls)).toEqual({ expected_override: 13 })
})

test('a dispute can be resolved with either number', async () => {
  const calls = mockFetch({ 'PATCH /api/v1/seasons/3': { body: {} } })
  renderWithProviders(<SeasonOverride seriesId={1} season={season} />)
  fireEvent.click(screen.getByRole('button', { name: '12 übernehmen (Sonarr)' }))
  await waitFor(() => expect(body(calls)).toEqual({ expected_override: 12 }))
  fireEvent.click(screen.getByRole('button', { name: '24 übernehmen (AniList)' }))
  await waitFor(() => expect(body(calls)).toEqual({ expected_override: 24 }))
})

test('an existing override can be reset; errors are shown', async () => {
  const calls = mockFetch({
    'PATCH /api/v1/seasons/3': { status: 400, body: { error: { code: 'validation' } } },
  })
  renderWithProviders(
    <SeasonOverride seriesId={1} season={{ ...season, disputed: false, expected_override: 20 }} />,
  )
  expect(screen.getByLabelText('Folgenzahl selbst festlegen')).toHaveValue(20)
  fireEvent.click(screen.getByRole('button', { name: 'Zurücksetzen' }))
  await waitFor(() => expect(body(calls)).toEqual({ expected_override: null }))
  expect(await screen.findByText('Bitte die markierten Felder prüfen.')).toBeInTheDocument()
})
