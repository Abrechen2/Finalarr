import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Toggle } from '../components/Toggle'
import { ApiError, apiFetch, errorText } from '../lib/api'
import { EVENT_TYPES, type EventType } from '../lib/events'

const KINDS = ['telegram', 'discord', 'pushover', 'webhook', 'apprise'] as const
type Kind = (typeof KINDS)[number]
const FIELDS: Record<Kind, { name: string; secret?: boolean }[]> = {
  telegram: [{ name: 'bot_token', secret: true }, { name: 'chat_id' }],
  discord: [{ name: 'webhook_url', secret: true }],
  pushover: [
    { name: 'user_key', secret: true },
    { name: 'app_token', secret: true },
  ],
  webhook: [{ name: 'url' }],
  apprise: [{ name: 'url', secret: true }],
}

export interface ChannelView {
  id: number
  name: string
  kind: Kind
  target: string
  enabled: boolean
  language: 'de' | 'en'
  event_filter: EventType[]
}

const input = 'mt-1 w-full rounded-card border border-line bg-bg px-2 py-1.5 text-sm'
const button =
  'rounded-card border border-line px-3 py-1.5 text-sm text-muted hover:text-ink disabled:opacity-60'

export function ChannelForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const [kind, setKind] = useState<Kind>('telegram')
  const [name, setName] = useState('Telegram')
  const [language, setLanguage] = useState<'de' | 'en'>('de')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [events, setEvents] = useState<EventType[]>([])
  const body = () => ({ kind, name, language, fields, event_filter: events })
  const test = useMutation({
    mutationFn: () =>
      apiFetch('/api/v1/channels/test', { method: 'POST', body: JSON.stringify(body()) }),
  })
  const save = useMutation({
    mutationFn: () =>
      apiFetch('/api/v1/channels', { method: 'POST', body: JSON.stringify(body()) }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['channels'] })
      onDone()
    },
  })
  const fieldErrors = [test.error, save.error].reduce<Record<string, string>>(
    (acc, error) => (error instanceof ApiError ? { ...acc, ...error.fields } : acc),
    {},
  )

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate()
  }

  return (
    <form onSubmit={submit} className="mt-4 rounded-card border border-line p-4">
      <div className="grid gap-3 min-[600px]:grid-cols-3">
        <label className="text-sm">
          {t('channel.kind')}
          <select
            value={kind}
            onChange={(e) => {
              const next = e.target.value as Kind
              setKind(next)
              setFields({})
              setName(t(`channel.kinds.${next}`))
            }}
            className={input}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`channel.kinds.${k}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          {t('channel.name')}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className={input}
          />
        </label>
        <label className="text-sm">
          {t('channel.language')}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as 'de' | 'en')}
            className={input}
          >
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </label>
      </div>
      <div className="mt-3 grid gap-3 min-[600px]:grid-cols-2">
        {FIELDS[kind].map((field) => (
          <label key={field.name} className="text-sm">
            {t(`channel.fields.${field.name}`)}
            <input
              type={field.secret ? 'password' : 'text'}
              autoComplete="off"
              required
              value={fields[field.name] ?? ''}
              onChange={(e) => setFields({ ...fields, [field.name]: e.target.value })}
              aria-invalid={Boolean(fieldErrors[`fields.${field.name}`])}
              className={input}
            />
            {fieldErrors[`fields.${field.name}`] && (
              <span className="mt-1 block text-xs text-bad">
                {fieldErrors[`fields.${field.name}`]}
              </span>
            )}
          </label>
        ))}
      </div>
      <fieldset className="mt-3">
        <legend className="text-sm">{t('channel.events')}</legend>
        <p className="text-xs text-muted">{t('channel.eventsHint')}</p>
        <div className="flex flex-wrap gap-x-4">
          {EVENT_TYPES.map((type) => (
            <Toggle
              key={type}
              label={t(`event.types.${type}`)}
              checked={events.includes(type)}
              onChange={(on) =>
                setEvents(on ? [...events, type] : events.filter((e) => e !== type))
              }
            />
          ))}
        </div>
      </fieldset>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={button}
          disabled={test.isPending}
          onClick={() => test.mutate()}
        >
          {t('channel.test')}
        </button>
        <button
          type="submit"
          disabled={save.isPending}
          className="rounded-card bg-accent px-3 py-1.5 text-sm font-medium text-white"
        >
          {t('channel.save')}
        </button>
        <button type="button" className={button} onClick={onDone}>
          {t('channel.cancel')}
        </button>
        <span role="status" className="text-sm">
          {test.isSuccess && <span className="text-ok">{t('channel.testOk')}</span>}
          {(test.isError || save.isError) && (
            <span className="text-bad">{errorText(t, save.error ?? test.error)}</span>
          )}
        </span>
      </div>
    </form>
  )
}

function ChannelRow({ channel }: { channel: ChannelView }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: ['channels'] })
  const patch = useMutation({
    mutationFn: (body: Partial<ChannelView>) =>
      apiFetch(`/api/v1/channels/${channel.id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: refresh,
  })
  const remove = useMutation({
    mutationFn: () => apiFetch(`/api/v1/channels/${channel.id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  })
  const test = useMutation({
    mutationFn: () => apiFetch(`/api/v1/channels/${channel.id}/test`, { method: 'POST' }),
  })
  const filter = channel.event_filter.length
    ? channel.event_filter.map((e) => t(`event.types.${e}`)).join(', ')
    : t('channel.all')
  return (
    <li className="rounded-card border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">{channel.name}</p>
          <p className="text-xs text-muted">
            {t(`channel.kinds.${channel.kind}`)} ·{' '}
            <span className="font-mono">{channel.target}</span> · {channel.language.toUpperCase()} ·{' '}
            {filter}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Toggle
            label={t('channel.enabled')}
            checked={channel.enabled}
            disabled={patch.isPending}
            onChange={(enabled) => patch.mutate({ enabled })}
          />
          <button
            type="button"
            className={button}
            disabled={test.isPending}
            onClick={() => test.mutate()}
          >
            {t('channel.test')}
          </button>
          <button
            type="button"
            className={button}
            onClick={() => {
              if (window.confirm(t('channel.deleteConfirm', { name: channel.name })))
                remove.mutate()
            }}
          >
            {t('channel.delete')}
          </button>
        </div>
      </div>
      <p role="status" className="mt-1 text-xs">
        {test.isSuccess && <span className="text-ok">{t('channel.testOk')}</span>}
        {test.isError && <span className="text-bad">{errorText(t, test.error)}</span>}
      </p>
    </li>
  )
}

export function ChannelsSettings() {
  const { t } = useTranslation()
  const [adding, setAdding] = useState(false)
  const channels = useQuery({
    queryKey: ['channels'],
    queryFn: () => apiFetch<ChannelView[]>('/api/v1/channels'),
  })
  return (
    <section className="rounded-card border border-line bg-surface p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-medium">{t('channel.title')}</h2>
        {!adding && (
          <button type="button" className={button} onClick={() => setAdding(true)}>
            {t('channel.add')}
          </button>
        )}
      </div>
      {channels.isError && (
        <p role="alert" className="mt-3 text-sm text-bad">
          {errorText(t, channels.error)}
        </p>
      )}
      {channels.data?.length === 0 && !adding && (
        <p className="mt-3 text-sm text-muted">{t('channel.empty')}</p>
      )}
      <ul className="mt-3 flex flex-col gap-2">
        {channels.data?.map((c) => (
          <ChannelRow key={c.id} channel={c} />
        ))}
      </ul>
      {adding && <ChannelForm onDone={() => setAdding(false)} />}
    </section>
  )
}
