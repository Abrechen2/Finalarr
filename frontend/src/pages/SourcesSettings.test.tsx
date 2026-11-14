import { fireEvent, screen, waitFor } from '@testing-library/react'
import i18n from '../i18n'
import { mockFetch, renderWithProviders } from '../test/render'
import { AboutPage } from './AboutPage'
import { SourcesSettings } from './SourcesSettings'

afterEach(() => vi.unstubAllGlobals())
beforeEach(() => i18n.changeLanguage('de'))

const source = (id: string, name: string, extra = {}) => ({
  id,
  name,
  url: `https://${id}.example`,
  terms_url: `https://${id}.example/terms`,
  core: false,
  needs_key: false,
  configured: true,
  enabled: true,
  ...extra,
})

test('sources list explains use and terms and switches a source off', async () => {
  const calls = mockFetch({
    'GET /api/v1/sources': {
      body: [
        source('anilist', 'AniList', { core: true }),
        source('tvmaze', 'TVmaze'),
        source('tmdb', 'TMDB', { needs_key: true, configured: false }),
      ],
    },
    'PATCH /api/v1/sources/tvmaze': { body: source('tvmaze', 'TVmaze', { enabled: false }) },
  })
  renderWithProviders(<SourcesSettings />)
  expect(await screen.findByRole('link', { name: 'TVmaze' })).toHaveAttribute(
    'href',
    'https://tvmaze.example',
  )
  expect(screen.getByText(/CC BY-SA 4.0/)).toBeInTheDocument()
  expect(screen.getByText('Grundfunktion')).toBeInTheDocument()
  expect(screen.getByText('Schlüssel fehlt')).toBeInTheDocument()
  expect(screen.getByLabelText('TMDB verwenden')).toBeDisabled()
  fireEvent.click(screen.getByLabelText('TVmaze verwenden'))
  await waitFor(() =>
    expect(
      calls.some((c) => c.url === '/api/v1/sources/tvmaze' && c.init?.method === 'PATCH'),
    ).toBe(true),
  )
  const patch = calls.find((c) => c.init?.method === 'PATCH')
  expect(JSON.parse(String(patch?.init?.body))).toEqual({ enabled: false })
})

test('about page credits the data sources with the TMDB notice', async () => {
  mockFetch({ 'GET /health': { body: { version: '0.3.0' } } })
  renderWithProviders(<AboutPage />)
  expect(await screen.findByText('0.3.0')).toBeInTheDocument()
  expect(screen.getByAltText('TMDB')).toBeInTheDocument()
  expect(
    screen.getByText(
      'Dieses Produkt nutzt die TMDB-API, ist aber nicht von TMDB unterstützt oder zertifiziert.',
    ),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: 'TVmaze (Daten unter CC BY-SA 4.0)' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Lizenzen der mitgelieferten/ })).toHaveAttribute(
    'href',
    '/licenses/INDEX.txt',
  )
})
