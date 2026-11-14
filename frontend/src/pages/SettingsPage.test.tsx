import { fireEvent, screen, waitFor } from '@testing-library/react'
import i18n from '../i18n'
import { mockFetch, renderWithProviders } from '../test/render'
import { SettingsPage } from './SettingsPage'

const RULES = {
  renotify_on_growth: false,
  renotify_after_file_loss: false,
  include_specials_default: false,
  respect_monitoring_default: true,
  stable_runs: 2,
  reconcile_interval_minutes: 30,
  news_feeds: true,
  series_news_web: true,
}

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18n.changeLanguage('de')
})

function openAppearance() {
  mockFetch({ 'GET /api/v1/settings': { body: RULES } })
  renderWithProviders(<SettingsPage />)
  fireEvent.click(screen.getByRole('tab', { name: 'Darstellung' }))
}

test('switching to English translates the page', async () => {
  openAppearance()
  fireEvent.click(screen.getByLabelText('English'))
  expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
})

test('choosing light sets the theme on the document', () => {
  openAppearance()
  fireEvent.click(screen.getByLabelText('Hell'))
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(screen.getByLabelText('Hell')).toBeChecked()
})

test('rules load and a toggle saves immediately', async () => {
  const calls = mockFetch({
    'GET /api/v1/settings': { body: RULES },
    'PATCH /api/v1/settings': { body: { ...RULES, renotify_on_growth: true } },
  })
  renderWithProviders(<SettingsPage />)
  fireEvent.click(screen.getByRole('tab', { name: 'Regeln' }))
  const toggle = await screen.findByLabelText(/Erneut melden, wenn eine komplette Staffel wächst/)
  fireEvent.click(toggle)
  expect(await screen.findByText('Gespeichert.')).toBeInTheDocument()
  expect(JSON.parse(String(calls.at(-1)?.init?.body))).toEqual({ renotify_on_growth: true })
  expect(toggle).toBeChecked()
})

test('number rules save on blur only when valid and changed', async () => {
  const calls = mockFetch({
    'GET /api/v1/settings': { body: RULES },
    'PATCH /api/v1/settings': { body: { ...RULES, reconcile_interval_minutes: 15 } },
  })
  renderWithProviders(<SettingsPage />)
  fireEvent.click(screen.getByRole('tab', { name: 'Regeln' }))
  const interval = await screen.findByLabelText('Abgleich mit Sonarr alle … Minuten')
  fireEvent.blur(interval, { target: { value: '2' } })
  fireEvent.blur(interval, { target: { value: '30' } })
  expect(calls.filter((c) => c.init?.method === 'PATCH')).toHaveLength(0)
  fireEvent.blur(interval, { target: { value: '15' } })
  await waitFor(() => expect(calls.filter((c) => c.init?.method === 'PATCH')).toHaveLength(1))
})

test('rule errors are shown', async () => {
  mockFetch({ 'GET /api/v1/settings': { status: 500, body: {} } })
  renderWithProviders(<SettingsPage />)
  fireEvent.click(screen.getByRole('tab', { name: 'Regeln' }))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})
