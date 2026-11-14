import { airTime, relativeTime } from './format'

const now = new Date('2026-11-14T12:00:00Z')

test.each([
  ['2026-11-17T12:00:00Z', 'de', 'in 3 Tagen'],
  ['2026-11-15T12:00:00Z', 'de', 'morgen'],
  ['2026-11-14T17:00:00Z', 'en', 'in 5 hours'],
  ['2026-11-14T12:20:00Z', 'en', 'in 20 minutes'],
  ['2027-01-04T12:00:00Z', 'de', 'in 51 Tagen'],
  ['2027-04-14T12:00:00Z', 'de', 'in 5 Monaten'],
  ['2028-11-14T12:00:00Z', 'en', 'in 2 years'],
])('countdown to %s (%s)', (iso, language, text) => {
  expect(relativeTime(iso, language, now)).toBe(text)
})

test('air time has weekday and time', () => {
  expect(airTime('2026-11-21T16:00:00Z', 'de')).toMatch(/^Sa\.?, 21\.11\.,? \d{2}:00$/)
})
