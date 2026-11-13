import { dayKey, groupByDay, monthGrid, shiftMonth } from './calendar'

test('month grid starts on Monday and covers six weeks', () => {
  const days = monthGrid(2026, 10) // November 2026, starts on a Sunday
  expect(days).toHaveLength(42)
  expect(dayKey(days[0])).toBe('2026-10-26')
  expect(dayKey(days[6])).toBe('2026-11-01')
  expect(dayKey(days[41])).toBe('2026-12-06')
})

test('shiftMonth wraps years', () => {
  expect(shiftMonth(2026, 11, 1)).toEqual([2027, 0])
  expect(shiftMonth(2027, 0, -1)).toEqual([2026, 11])
})

test('entries are grouped by local day; all-day entries by their date', () => {
  const groups = groupByDay([
    { start: '2026-11-20T15:00:00+00:00', all_day: false },
    { start: '2026-11-20T23:30:00+00:00', all_day: false },
    { start: '2027-02-14', all_day: true },
  ])
  expect((groups['2026-11-20']?.length ?? 0) + (groups['2026-11-21']?.length ?? 0)).toBe(2)
  expect(groups['2027-02-14']).toHaveLength(1)
})
