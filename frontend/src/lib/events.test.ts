import i18n from '../i18n'
import { episodeRanges, formatEvent } from './events'

const t = i18n.t.bind(i18n)

test.each([
  [[1, 2, 3, 5, 7, 8], 'E01–E03, E05, E07–E08'],
  [[4], 'E04'],
  [[3, 1, 2, 2], 'E01–E03'],
  [[], ''],
])('ranges %o', (numbers, text) => {
  expect(episodeRanges(numbers)).toBe(text)
})

const payload = { title: 'Slime', season: 3, have: 7, expected: 12 }

test('German messages for every type', () => {
  expect(formatEvent(t, 'episodes_available', { ...payload, episodes: [5, 6, 7] })).toBe(
    'Slime S03 E05–E07 verfügbar (7/12)',
  )
  expect(formatEvent(t, 'finale_available', { ...payload, finale_number: 12 })).toBe(
    'Finale: Slime S03E12 verfügbar (7/12)',
  )
  expect(formatEvent(t, 'season_complete', { ...payload, have: 12 })).toBe(
    'Slime Staffel 3 komplett (12/12)',
  )
  expect(formatEvent(t, 'part_complete', { ...payload, part: 1 })).toBe(
    'Slime Staffel 3 Teil 1 komplett',
  )
  expect(
    formatEvent(t, 'season_announced', {
      title: 'Frieren',
      season: 2,
      expected: 12,
      first_air: '2027-04-05',
    }),
  ).toBe('Frieren: Staffel 2 angekündigt (Start 5.4.2027, 12 Folgen)')
  expect(formatEvent(t, 'season_announced', { title: 'Frieren', season: 2 })).toBe(
    'Frieren: Staffel 2 angekündigt',
  )
})

test('missing fields degrade gracefully', () => {
  expect(formatEvent(t, 'season_complete', {})).toMatch(/^\? Staffel .*komplett \(0\/\?\)$/)
})

test('English uses the English date format', async () => {
  await i18n.changeLanguage('en')
  expect(
    formatEvent(
      i18n.t.bind(i18n),
      'season_announced',
      { title: 'F', season: 2, expected: 12, first_air: '2027-04-05' },
      'en',
    ),
  ).toBe('F: season 2 announced (starts 05/04/2027, 12 episodes)')
  await i18n.changeLanguage('de')
})

test('part complete in parts mode reads like a season of its own', () => {
  expect(
    formatEvent(t, 'part_complete', {
      ...payload,
      part: 2,
      part_title: 'Mushoku II Part 2',
      parts_mode: 'parts',
    }),
  ).toBe('Mushoku II Part 2 komplett')
})

test('sequel announcements show the year when only the year is known', () => {
  const base = { title: 'Mushoku Tensei', sequel_title: 'Mushoku Tensei III Part 2' }
  expect(formatEvent(t, 'sequel_announced', { ...base, first_air: '2027-01-01' })).toBe(
    'Mushoku Tensei: Fortsetzung angekündigt – Mushoku Tensei III Part 2 (Start 2027)',
  )
  expect(formatEvent(t, 'sequel_announced', { ...base, first_air: '2027-07-04' })).toBe(
    'Mushoku Tensei: Fortsetzung angekündigt – Mushoku Tensei III Part 2 (Start 4.7.2027)',
  )
  expect(formatEvent(t, 'sequel_announced', base)).toBe(
    'Mushoku Tensei: Fortsetzung angekündigt – Mushoku Tensei III Part 2',
  )
})

test('news mentions quote the headline', () => {
  expect(
    formatEvent(t, 'news_mention', { title: 'Mushoku Tensei', headline: 'Part 2 in 2027' }),
  ).toBe('Mushoku Tensei in den News: Part 2 in 2027')
})

test('postponed episode names old and new date', async () => {
  await i18n.changeLanguage('de')
  const delayed = { title: 'Slime', season: 4, episode: 7, old: '2026-11-20T15:00:00Z' }
  expect(formatEvent(t, 'episode_delayed', { ...delayed, new: '2026-12-04T15:00:00Z' }, 'de')).toBe(
    'Slime S04E07 verschoben: 20.11.2026 → 04.12.2026',
  )
  expect(formatEvent(t, 'episode_delayed', { ...delayed, new: null }, 'de')).toBe(
    'Slime S04E07 verschoben: 20.11.2026 → offen',
  )
})
