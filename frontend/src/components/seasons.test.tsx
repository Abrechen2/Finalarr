import { screen } from '@testing-library/react'
import type { EpisodeDetail, SeasonSummary } from '../lib/types'
import { renderWithProviders } from '../test/render'
import { EpisodeGrid } from './EpisodeGrid'
import { SeasonProgress } from './SeasonProgress'
import { StateBadge } from './StateBadge'

const season: SeasonSummary = {
  id: 1,
  number: 3,
  state: 'airing',
  expected: 12,
  have: 7,
  disputed: false,
}

test('progress shows have/expected and the state', () => {
  renderWithProviders(<SeasonProgress season={season} />)
  expect(screen.getByText('7/12')).toBeInTheDocument()
  expect(screen.getByText('läuft')).toBeInTheDocument()
  const bar = screen.getByRole('progressbar', { name: 'Staffel 3' })
  expect(bar).toHaveAttribute('aria-valuenow', '7')
  expect(bar.firstElementChild).toHaveStyle({ width: '58%' })
})

test('unknown expected count shows a question mark', () => {
  renderWithProviders(<SeasonProgress season={{ ...season, expected: null, have: 2 }} />)
  expect(screen.getByText('2/?')).toBeInTheDocument()
})

test('a dispute wins over the state in the badge', () => {
  renderWithProviders(<StateBadge state="aired" disputed />)
  expect(screen.getByText('Folgenzahl unklar')).toBeInTheDocument()
})

const episode = (number: number, extra: Partial<EpisodeDetail> = {}): EpisodeDetail => ({
  id: number,
  number,
  absolute_number: null,
  title: `E${number}`,
  air_date: '2026-01-05T00:00:00Z',
  monitored: true,
  has_file: false,
  finale_type: null,
  ...extra,
})

test('grid labels every episode for screen readers, finale included', () => {
  renderWithProviders(
    <EpisodeGrid
      season={3}
      now={new Date('2026-02-01')}
      episodes={[
        episode(1, { has_file: true }),
        episode(2),
        episode(3, { air_date: '2026-06-01T00:00:00Z', finale_type: 'season' }),
      ]}
    />,
  )
  expect(screen.getByLabelText('S03E01: vorhanden')).toBeInTheDocument()
  expect(screen.getByLabelText('S03E02: ausgestrahlt, Datei fehlt')).toBeInTheDocument()
  expect(
    screen.getByLabelText('S03E03: noch nicht ausgestrahlt, Staffelfinale'),
  ).toBeInTheDocument()
})
