import { fireEvent, screen, waitFor } from '@testing-library/react'
import { mockFetch, renderWithProviders } from '../test/render'
import { type ChannelView, ChannelsSettings } from './ChannelsSettings'

afterEach(() => vi.unstubAllGlobals())

const channel: ChannelView = {
  id: 1,
  name: 'Handy',
  kind: 'telegram',
  target: 'tgram://***',
  enabled: true,
  language: 'de',
  event_filter: ['season_complete'],
  quiet_hours: { start: '22:00', end: '07:00' },
}

function lastBody(calls: { init?: RequestInit }[]) {
  return JSON.parse(String(calls.at(-1)?.init?.body))
}

function patchBody(calls: { init?: RequestInit }[]) {
  return JSON.parse(String(calls.find((c) => c.init?.method === 'PATCH')?.init?.body))
}

test('lists channels without secrets and can toggle, test and delete', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = mockFetch({
    'GET /api/v1/channels': { body: [channel] },
    'PATCH /api/v1/channels/1': { body: { ...channel, enabled: false } },
    'POST /api/v1/channels/1/test': {
      status: 502,
      body: { error: { code: 'channel_failed', message: 'Unauthorized' } },
    },
    'DELETE /api/v1/channels/1': { status: 204, body: {} },
  })
  renderWithProviders(<ChannelsSettings />)
  expect(await screen.findByText('Handy')).toBeInTheDocument()
  expect(screen.getByText(/tgram:\/\/\*\*\*/)).toBeInTheDocument()
  expect(screen.getByText(/Komplett · Ruhezeit 22:00–07:00/)).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('aktiv'))
  await waitFor(() => {
    const patch = calls.find((c) => c.init?.method === 'PATCH')
    expect(JSON.parse(String(patch?.init?.body))).toEqual({ enabled: false })
  })
  fireEvent.click(screen.getByRole('button', { name: 'Testnachricht senden' }))
  expect(
    await screen.findByText('Der Dienst hat die Nachricht abgelehnt: Unauthorized'),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Löschen' }))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'DELETE')).toBe(true))
})

test('empty state and adding a Telegram channel with test and field errors', async () => {
  const calls = mockFetch({
    'GET /api/v1/channels': { body: [] },
    'POST /api/v1/channels/test': {
      status: 400,
      body: {
        error: {
          code: 'validation',
          message: 'x',
          fields: { 'fields.bot_token': 'Token looks wrong' },
        },
      },
    },
    'POST /api/v1/channels': { status: 201, body: channel },
  })
  renderWithProviders(<ChannelsSettings />)
  expect(await screen.findByText(/Noch kein Kanal/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Kanal hinzufügen' }))
  fireEvent.change(screen.getByLabelText('Bot-Token (von @BotFather)'), {
    target: { value: 'bad' },
  })
  fireEvent.change(screen.getByLabelText(/Chat-ID/), { target: { value: '-100' } })
  fireEvent.click(screen.getByLabelText('Komplett'))
  fireEvent.click(screen.getByRole('button', { name: 'Testnachricht senden' }))
  expect(await screen.findByText('Token looks wrong')).toBeInTheDocument()
  expect(lastBody(calls)).toEqual({
    kind: 'telegram',
    name: 'Telegram',
    language: 'de',
    fields: { bot_token: 'bad', chat_id: '-100' },
    event_filter: ['season_complete'],
    quiet_hours: null,
  })
  fireEvent.change(screen.getByLabelText('von'), { target: { value: '22:00' } })
  fireEvent.change(screen.getByLabelText('bis'), { target: { value: '07:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  await waitFor(() => {
    const save = calls.find((c) => c.url === '/api/v1/channels' && c.init?.method === 'POST')
    expect(JSON.parse(String(save?.init?.body)).quiet_hours).toEqual({
      start: '22:00',
      end: '07:00',
    })
  })
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Speichern' })).not.toBeInTheDocument(),
  )
})

test('switching the service changes the fields and name', async () => {
  mockFetch({ 'GET /api/v1/channels': { body: [] } })
  renderWithProviders(<ChannelsSettings />)
  fireEvent.click(await screen.findByRole('button', { name: 'Kanal hinzufügen' }))
  fireEvent.change(screen.getByLabelText('Dienst'), { target: { value: 'pushover' } })
  expect(screen.getByLabelText('Name')).toHaveValue('Pushover')
  expect(screen.getByLabelText('Pushover User Key')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Sprache der Meldungen'), { target: { value: 'en' } })
  fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
  expect(screen.queryByLabelText('Dienst')).not.toBeInTheDocument()
})

test('channel list errors are shown', async () => {
  mockFetch({ 'GET /api/v1/channels': { status: 500, body: {} } })
  renderWithProviders(<ChannelsSettings />)
  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

test('editing a channel keeps the stored token unless a new one is entered', async () => {
  const calls = mockFetch({
    'GET /api/v1/channels': { body: [channel] },
    'PATCH /api/v1/channels/1': { body: { ...channel, name: 'Telegram' } },
  })
  renderWithProviders(<ChannelsSettings />)
  fireEvent.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
  const name = screen.getByLabelText('Name')
  expect(name).toHaveValue('Handy')
  expect(screen.getByLabelText('Komplett')).toBeChecked()
  expect(screen.getByLabelText('von')).toHaveValue('22:00')
  fireEvent.change(name, { target: { value: 'Telegram' } })
  fireEvent.click(screen.getByLabelText('Finale'))
  fireEvent.change(screen.getByLabelText('von'), { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'PATCH')).toBe(true))
  expect(patchBody(calls)).toEqual({
    name: 'Telegram',
    language: 'de',
    event_filter: ['season_complete', 'finale_available'],
    quiet_hours: null,
  })
  await waitFor(() => expect(screen.queryByLabelText('Name')).not.toBeInTheDocument())
})

test('a new token in the edit form is sent along', async () => {
  const calls = mockFetch({
    'GET /api/v1/channels': { body: [channel] },
    'PATCH /api/v1/channels/1': { body: channel },
  })
  renderWithProviders(<ChannelsSettings />)
  fireEvent.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
  expect(screen.getByLabelText(/^Bot-Token/)).toHaveAttribute(
    'placeholder',
    'Leer lassen, um den gespeicherten Wert zu behalten',
  )
  fireEvent.change(screen.getByLabelText(/^Bot-Token/), { target: { value: '123:ABC' } })
  fireEvent.change(screen.getByLabelText(/^Chat-ID/), { target: { value: '42' } })
  fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
  await waitFor(() => expect(calls.some((c) => c.init?.method === 'PATCH')).toBe(true))
  expect(patchBody(calls).fields).toEqual({ bot_token: '123:ABC', chat_id: '42' })
})
