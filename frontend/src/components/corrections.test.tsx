import { fireEvent, screen, waitFor } from '@testing-library/react'
import i18n from '../i18n'
import type { SeasonDetail, SeriesDetail } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/render'
import { CountSources } from './CountSources'
import { WatchCorrector } from './WatchCorrector'

afterEach(() => vi.unstubAllGlobals())
beforeEach(() => i18n.changeLanguage('de'))

const season = {
  id: 9,
  number: 1,
  state: 'airing',
  expected: null,
  have: 2,
  disputed: true,
  parts: [],
  episodes: [1, 2, 3].map((n) => ({
    id: n,
    number: n,
    absolute_number: null,
    title: `Ep ${n}`,
    air_date: '2026-10-01T15:00:00Z',
    monitored: true,
    has_file: n < 3,
    finale_type: null,
  })),
} as unknown as SeasonDetail

const series = {
  id: 5,
  watch: {
    enabled: true,
    users: [],
    episodes: { '1x1': [7] },
    viewers: [
      { id: 7, name: 'Dennis', server: 'Emby' },
      { id: 8, name: 'Anna', server: 'Emby' },
    ],
    corrected: ['1x2'],
    unwatched_on_disk: 0,
    next_unwatched: null,
  },
} as unknown as SeriesDetail

test('clicking an episode corrects its watched state for the chosen person', async () => {
  const calls = mockFetch({
    'POST /api/v1/series/5/watched': { body: { ...series.watch, corrected: [] } },
  })
  renderWithProviders(<WatchCorrector series={series} season={season} />)
  expect(screen.getByRole('button', { name: /S01E01: .*gesehen von Dennis/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /S01E02: .*manuell korrigiert/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^S01E03/ }))
  fireEvent.change(screen.getByLabelText('für'), { target: { value: '8' } })
  fireEvent.click(screen.getByRole('button', { name: 'Bis hier gesehen' }))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({
    user_id: 8,
    episodes: [
      [1, 1],
      [1, 2],
      [1, 3],
    ],
    watched: true,
  })
  await waitFor(() => expect(screen.queryByText('Bis hier gesehen')).not.toBeInTheDocument())
})

test('a corrected episode can be taken back', async () => {
  const calls = mockFetch({ 'POST /api/v1/series/5/watched': { body: series.watch } })
  renderWithProviders(<WatchCorrector series={series} season={season} />)
  fireEvent.click(screen.getByRole('button', { name: /^S01E02/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Korrektur zurücknehmen' }))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(JSON.parse(String(calls[0].init?.body))).toMatchObject({
    user_id: 7,
    episodes: [[1, 2]],
    watched: null,
  })
})

test('without a media server the grid is not clickable', () => {
  const plain = { ...series, watch: { ...series.watch, enabled: false } } as SeriesDetail
  renderWithProviders(<WatchCorrector series={plain} season={season} />)
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(screen.getByLabelText(/^S01E01/)).toBeInTheDocument()
})

test('count sources explain an unclear episode count', async () => {
  mockFetch({
    'GET /api/v1/seasons/9/count-sources': {
      body: {
        expected: null,
        expected_source: null,
        disputed: true,
        state: 'airing',
        last_evaluated_at: '2026-11-14T10:00:00Z',
        sources: [
          {
            source: 'sonarr',
            count: 12,
            url: 'http://sonarr/series/x',
            detail: { listed: 14, unmonitored: 2, aired: 10, on_disk: 9, finale: null },
          },
          {
            source: 'anilist',
            count: 24,
            entries: [
              {
                id: 10,
                title: 'Part 1',
                episodes: 12,
                status: 'FINISHED',
                url: 'https://anilist.co/anime/10',
              },
              {
                id: 11,
                title: null,
                episodes: null,
                status: null,
                url: 'https://anilist.co/anime/11',
              },
            ],
            parts: [{ index: 2, from: 13, to: 24, title: 'Part 2' }],
          },
          { source: 'tvmaze', count: 25, url: 'https://www.tvmaze.com/shows/7' },
        ],
      },
    },
  })
  renderWithProviders(<CountSources season={season} />)
  expect(
    await screen.findByText('Finalarr kennt die Folgenzahl noch nicht und wartet mit „komplett“.'),
  ).toBeInTheDocument()
  expect(
    screen.getByText(
      '14 gelistet, 10 ausgestrahlt, 9 vorhanden · 2 davon nicht überwacht, sie zählen nicht mit',
    ),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Part 1: 12 Folgen (abgeschlossen)' })).toHaveAttribute(
    'href',
    'https://anilist.co/anime/10',
  )
  expect(screen.getByText('Eintrag 11')).toBeInTheDocument()
  expect(screen.getByText('Teil 2: Folge 13–24')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'TVmaze' })).toBeInTheDocument()
  expect(screen.getByText('25')).toBeInTheDocument()
})

test('a clear count stays folded until opened', () => {
  const calls = mockFetch({})
  renderWithProviders(<CountSources season={{ ...season, disputed: false, expected: 3 }} />)
  expect(calls).toHaveLength(0)
})
