import { episodeCell, isSeasonFinale, pad } from './episodes'
import type { EpisodeDetail } from './types'

const base: EpisodeDetail = {
  id: 1,
  number: 1,
  absolute_number: null,
  title: '',
  air_date: '2026-01-05T15:00:00Z',
  monitored: true,
  has_file: false,
  finale_type: null,
}
const now = new Date('2026-02-01T00:00:00Z')

test.each([
  [{ has_file: true }, 'file'],
  [{}, 'missing'],
  [{ air_date: '2026-03-01T00:00:00Z' }, 'future'],
  [{ air_date: null }, 'future'],
])('episode %o is %s', (override, cell) => {
  expect(episodeCell({ ...base, ...override }, now)).toBe(cell)
})

test('season and series finales count, midseason does not', () => {
  expect(isSeasonFinale({ ...base, finale_type: 'season' })).toBe(true)
  expect(isSeasonFinale({ ...base, finale_type: 'series' })).toBe(true)
  expect(isSeasonFinale({ ...base, finale_type: 'midseason' })).toBe(false)
})

test('pad', () => {
  expect(pad(3)).toBe('03')
  expect(pad(12)).toBe('12')
})
