import { fireEvent, render, screen } from '@testing-library/react'
import i18n from '../i18n'
import { mockFetch, renderWithProviders } from '../test/render'
import { EpisodeGrid } from './EpisodeGrid'
import { SeriesExtras } from './SeriesExtras'
import { SeriesNews } from './SeriesNews'
import { WaitingCard } from './WaitingCard'

afterEach(() => vi.unstubAllGlobals())
beforeEach(() => i18n.changeLanguage('de'))

test.each([
  [
    { key: 'airing', season: 2, have: 3, expected: 12 },
    'Staffel 2 läuft: 3 von 12 Folgen sind da.',
  ],
  [
    { key: 'missing', season: 2, have: 3, expected: 12, missing: 1 },
    'Staffel 2: 1 ausgestrahlte Folge fehlt noch in der Bibliothek.',
  ],
  [
    { key: 'missing', season: 2, have: 3, expected: 12, missing: 3 },
    'Staffel 2: 3 ausgestrahlte Folgen fehlen noch in der Bibliothek.',
  ],
  [
    { key: 'renewed_open', season: 3, sequel_title: null, first_air: null },
    'Staffel 3 ist angekündigt, der Termin ist noch offen.',
  ],
  [
    { key: 'announced', season: null, sequel_title: 'Slime 3', first_air: '2027-01-01' },
    'Slime 3 ist angekündigt: Start 2027.',
  ],
  [
    { key: 'announced', season: 4, sequel_title: null, first_air: '2027-04-05' },
    'Staffel 4 ist angekündigt: Start 05.04.2027.',
  ],
  [{ key: 'ended' }, 'Die Serie ist abgeschlossen.'],
] as const)('waiting sentence %#', (waiting, text) => {
  render(<WaitingCard waiting={waiting} />)
  expect(screen.getByText(text)).toBeInTheDocument()
})

test('no card for unfollowed series', () => {
  const { container } = render(<WaitingCard waiting={{ key: 'not_followed' }} />)
  expect(container).toBeEmptyDOMElement()
})

const EXTRAS = {
  next_episode: {
    season: 4,
    episode: 7,
    at: new Date(Date.now() + 2 * 86_400_000 + 60_000).toISOString(),
    source: 'anilist',
  },
  trailer: { youtube_id: 'abc123' },
  channel: 'Tokyo MX',
  watch: [
    { name: 'Crunchyroll', url: 'https://cr/slime', source: 'anilist' },
    { name: 'Netflix', url: 'https://tmdb/watch', source: 'tmdb' },
  ],
  watch_region: 'DE',
  dub: {
    premiere: null,
    next: '2026-11-20T18:30:00Z',
    delayed_until: null,
    delay_note: '',
    url: 'https://animeschedule.net/anime/slime',
  },
  errors: ['tvmaze'],
}

test('extras: countdown, channel, watch chips, dub and click-to-load trailer', async () => {
  mockFetch({ 'GET /api/v1/series/3/extras': { body: EXTRAS } })
  renderWithProviders(<SeriesExtras seriesId={3} title="Slime" />)
  expect(await screen.findByText('Nächste Folge: S04E07 übermorgen')).toBeInTheDocument()
  expect(screen.getByText('laut AniList')).toBeInTheDocument()
  expect(screen.getByText('Läuft bei Tokyo MX')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Crunchyroll' })).toHaveAttribute(
    'href',
    'https://cr/slime',
  )
  expect(screen.getByText(/Daten von JustWatch über TMDB/)).toBeInTheDocument()
  expect(screen.getByText(/Englische Synchro/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Daten: AnimeSchedule.net' })).toBeInTheDocument()
  expect(screen.getByText('Nicht alle Quellen waren erreichbar.')).toBeInTheDocument()
  expect(screen.queryByTitle('Trailer: Slime')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Trailer abspielen' }))
  expect(screen.getByTitle('Trailer: Slime')).toHaveAttribute(
    'src',
    'https://www.youtube-nocookie.com/embed/abc123?autoplay=1',
  )
})

test('extras without anything to show render nothing', async () => {
  const calls = mockFetch({
    'GET /api/v1/series/3/extras': {
      body: {
        next_episode: null,
        trailer: null,
        channel: null,
        watch: [],
        watch_region: null,
        dub: null,
        errors: [],
      },
    },
  })
  const { container } = renderWithProviders(<SeriesExtras seriesId={3} title="Slime" />)
  await vi.waitFor(() => expect(calls).toHaveLength(1))
  expect(container).toBeEmptyDOMElement()
})

test('news items show their type and evidence', async () => {
  mockFetch({
    'GET /api/v1/series/3/news?lang=de': {
      body: {
        web_enabled: true,
        web_error: false,
        items: [
          {
            kind: 'event',
            event_type: 'news_mention',
            published: '2026-11-13T10:00:00+00:00',
            payload: {
              title: 'Re:ZERO',
              headline: 'Re:ZERO erhält fünfte Staffel',
              news_kind: 'renewal',
              evidence: 'Die Serie erhält eine fünfte Staffel.',
              link: 'https://n/1',
            },
          },
          {
            kind: 'web',
            title: 'Re:ZERO Folge 7 verschoben',
            news_kind: 'delay',
            link: 'https://n/2',
            source: 'X',
            published: '2026-11-12T08:00:00+00:00',
          },
        ],
      },
    },
  })
  renderWithProviders(<SeriesNews seriesId={3} />)
  expect(await screen.findByText('Verlängerung')).toBeInTheDocument()
  expect(screen.getByText('Die Serie erhält eine fünfte Staffel.')).toBeInTheDocument()
  expect(screen.getByText('Verschiebung')).toHaveClass('text-bad')
})

test('postponed episodes are marked in the grid', () => {
  render(
    <EpisodeGrid
      season={4}
      now={new Date('2026-11-14T00:00:00Z')}
      episodes={[
        {
          id: 1,
          number: 7,
          absolute_number: null,
          title: 'Seven',
          air_date: '2026-12-04T15:00:00Z',
          monitored: true,
          has_file: false,
          finale_type: null,
          delayed_from: '2026-11-20T15:00:00Z',
        },
      ]}
    />,
  )
  expect(screen.getByLabelText(/S04E07: .*verschoben, vorher 20\.11\.2026/)).toBeInTheDocument()
})
