import { fireEvent, screen, waitFor } from '@testing-library/react'
import type { CalendarEntry } from '../lib/calendar'
import { mockFetch, renderWithProviders } from '../test/render'
import { CalendarPage } from './CalendarPage'
import { CalendarSettings } from './CalendarSettings'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const entry = (over: Partial<CalendarEntry>): CalendarEntry => ({
  uid: 'u1',
  kind: 'finale',
  title: 'Slime',
  season: 3,
  episode: 24,
  episode_title: 'Finale',
  start: '2026-11-20T15:00:00+00:00',
  all_day: false,
  series_id: 4,
  has_file: false,
  sequel_title: null,
  ...over,
})

function fixDate() {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-13T12:00:00Z'))
}

test('month view shows entries and navigates', async () => {
  fixDate()
  const calls = mockFetch({
    'GET /api/v1/calendar?start=2026-10-26&end=2026-12-06': {
      body: {
        entries: [
          entry({}),
          entry({
            uid: 'u2',
            kind: 'announcement',
            title: 'The Last of Us',
            episode: null,
            start: '2026-11-25',
            all_day: true,
            series_id: null,
          }),
        ],
      },
    },
    'GET /api/v1/calendar?start=2026-11-30&end=2027-01-10': { body: { entries: [] } },
  })
  renderWithProviders(<CalendarPage />)
  expect(await screen.findAllByText('S03E24 · Finale')).not.toHaveLength(0)
  expect(screen.getAllByText('The Last of Us')).not.toHaveLength(0)
  expect(screen.getAllByTitle('The Last of Us: S03 (angekündigt)')).not.toHaveLength(0)
  expect(screen.getAllByRole('link', { name: /Slime S03E24/ })[0]).toHaveAttribute(
    'href',
    '/series/4',
  )
  expect(screen.getByText('November 2026')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Nächster Monat' }))
  expect(await screen.findByText('In diesem Monat wartet nichts.')).toBeInTheDocument()
  expect(calls.map((c) => c.url)).toContain('/api/v1/calendar?start=2026-11-30&end=2027-01-10')
  fireEvent.click(screen.getByRole('button', { name: 'Heute' }))
  expect(await screen.findByText('November 2026')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
  expect(await screen.findByText('Oktober 2026')).toBeInTheDocument()
})

test('calendar errors are shown', async () => {
  fixDate()
  mockFetch({ 'GET /api/v1/calendar?start=2026-10-26&end=2026-12-06': { status: 500, body: {} } })
  renderWithProviders(<CalendarPage />)
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

const RULES = {
  renotify_on_growth: false,
  renotify_after_file_loss: false,
  include_specials_default: false,
  respect_monitoring_default: true,
  stable_runs: 2,
  reconcile_interval_minutes: 30,
  news_feeds: true,
  calendar_scope: 'milestones',
  calendar_hide_downloaded: true,
  calendar_announcements: true,
  calendar_days_back: 14,
  calendar_days_ahead: 120,
}

test('calendar settings save the scope and the feed can be switched on, copied and renewed', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const writeText = vi.fn(async () => undefined)
  Object.assign(navigator, { clipboard: { writeText } })
  const calls = mockFetch({
    'GET /api/v1/settings': { body: RULES },
    'PATCH /api/v1/settings': { body: { ...RULES, calendar_scope: 'finales' } },
    'GET /api/v1/calendar/feed': { body: { enabled: false, path: null } },
    'PUT /api/v1/calendar/feed': { body: { enabled: true, path: '/ical/abc.ics' } },
    'POST /api/v1/calendar/feed/rotate': { body: { enabled: true, path: '/ical/def.ics' } },
  })
  renderWithProviders(<CalendarSettings />)
  fireEvent.click(await screen.findByLabelText('Nur Staffelfinals'))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'PATCH')).toBe(true))
  fireEvent.click(screen.getByLabelText('Kalender-Feed aktiv'))
  expect(
    await screen.findByText(`${window.location.origin}/ical/abc.ics?lang=de`),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Adresse kopieren' }))
  await waitFor(() => expect(writeText).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('button', { name: 'Neue Adresse erzeugen' }))
  expect(
    await screen.findByText(`${window.location.origin}/ical/def.ics?lang=de`),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('Bereits vorhandene Folgen ausblenden'))
  fireEvent.click(screen.getByLabelText(/Angekündigte Starttermine/))
  fireEvent.blur(screen.getByLabelText('Feed: Tage voraus'), { target: { value: '200' } })
  await waitFor(() =>
    expect(calls.filter((c) => c.init?.method === 'PATCH').length).toBeGreaterThanOrEqual(4),
  )
})
