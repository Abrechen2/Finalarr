import { screen } from '@testing-library/react'
import { mockFetch, renderWithProviders } from '../test/render'
import { SeriesNews } from './SeriesNews'

afterEach(() => vi.unstubAllGlobals())

test('own announcements first, then web headlines with source and link', async () => {
  mockFetch({
    'GET /api/v1/series/3/news?lang=de': {
      body: {
        web_enabled: true,
        web_error: false,
        items: [
          {
            kind: 'event',
            event_type: 'sequel_announced',
            published: '2026-11-13T10:00:00+00:00',
            payload: {
              title: 'Mushoku Tensei',
              sequel_title: 'Mushoku III Part 2',
              first_air: '2027-01-01',
            },
          },
          {
            kind: 'web',
            title: 'Mushoku Tensei Staffel 3 Teil 2 startet 2027',
            link: 'https://news.google.com/a',
            source: 'Hypebeast',
            published: '2026-09-28T08:00:00+00:00',
          },
        ],
      },
    },
  })
  renderWithProviders(<SeriesNews seriesId={3} />)
  expect(
    await screen.findByText(/Fortsetzung angekündigt – Mushoku III Part 2 \(Start 2027\)/),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: 'Mushoku Tensei Staffel 3 Teil 2 startet 2027' }),
  ).toHaveAttribute('href', 'https://news.google.com/a')
  expect(screen.getByText('via Hypebeast')).toBeInTheDocument()
})

test('empty, switched off and failing web search', async () => {
  mockFetch({
    'GET /api/v1/series/3/news?lang=de': {
      body: { items: [], web_enabled: false, web_error: false },
    },
  })
  renderWithProviders(<SeriesNews seriesId={3} />)
  expect(await screen.findByText('Noch keine News zu dieser Serie.')).toBeInTheDocument()
  expect(screen.getByText(/Websuche nach News ist in den Regeln ausgeschaltet/)).toBeInTheDocument()
})

test('a failing search says so', async () => {
  mockFetch({
    'GET /api/v1/series/3/news?lang=de': {
      body: { items: [], web_enabled: true, web_error: true },
    },
  })
  renderWithProviders(<SeriesNews seriesId={3} />)
  expect(await screen.findByText('Die News-Suche ist gerade nicht erreichbar.')).toBeInTheDocument()
})

test('request errors are shown', async () => {
  mockFetch({ 'GET /api/v1/series/3/news?lang=de': { status: 500, body: {} } })
  renderWithProviders(<SeriesNews seriesId={3} />)
  expect(await screen.findByText(/Etwas ist schiefgelaufen/)).toBeInTheDocument()
})
