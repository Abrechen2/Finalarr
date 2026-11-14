import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Toggle } from '../components/Toggle'
import { ApiError, apiFetch, errorText } from '../lib/api'
import { formatDate } from '../lib/format'

type Kind = 'emby' | 'jellyfin' | 'plex'
const KINDS: Kind[] = ['emby', 'jellyfin', 'plex']
const KIND_NAMES: Record<Kind, string> = { emby: 'Emby', jellyfin: 'Jellyfin', plex: 'Plex' }
const DEFAULT_PORT: Record<Kind, string> = {
  emby: 'http://192.168.1.10:8096',
  jellyfin: 'http://192.168.1.10:8096',
  plex: 'http://192.168.1.10:32400',
}

export interface MediaServerView {
  id: number
  kind: Kind
  name: string
  url: string
  token: string
  enabled: boolean
  version: string | null
  last_sync_at: string | null
  last_error: string | null
  unmatched: string[]
  users: { id: number; name: string; selected: boolean; watched_episodes: number }[]
}

interface RuleSettings {
  auto_follow: boolean
  auto_follow_min_episodes: number
  auto_follow_days: number
}

const INPUT = 'w-full rounded-control border border-line bg-bg px-3 py-1.5 text-sm'
const BUTTON = 'rounded-control border border-line px-3 py-1.5 text-sm hover:border-accent'

function useServers() {
  return useQuery({
    queryKey: ['media-servers'],
    queryFn: () => apiFetch<MediaServerView[]>('/api/v1/media-servers'),
  })
}

function AddServer({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const [kind, setKind] = useState<Kind>('emby')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [token, setToken] = useState('')
  const body = () => JSON.stringify({ kind, name: name || KIND_NAMES[kind], url, token })
  const test = useMutation({
    mutationFn: () =>
      apiFetch<{ version: string }>('/api/v1/media-servers/test', { method: 'POST', body: body() }),
  })
  const save = useMutation({
    mutationFn: () => apiFetch('/api/v1/media-servers', { method: 'POST', body: body() }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['media-servers'] })
      onDone()
    },
  })
  const fields = save.error instanceof ApiError ? save.error.fields : {}
  return (
    <form
      className="flex flex-col gap-3 rounded-card border border-line p-4"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate()
      }}
    >
      <fieldset className="flex gap-2">
        <legend className="mb-1 text-xs text-muted">{t('media.kind')}</legend>
        {KINDS.map((option) => (
          <label key={option} className="flex items-center gap-1.5 text-sm">
            <input
              type="radio"
              name="kind"
              checked={kind === option}
              onChange={() => setKind(option)}
              className="accent-[var(--accent)]"
            />
            {KIND_NAMES[option]}
          </label>
        ))}
      </fieldset>
      <label className="text-sm">
        {t('media.name')}
        <input
          className={INPUT}
          value={name}
          placeholder={KIND_NAMES[kind]}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label className="text-sm">
        {t('media.url')}
        <input
          className={INPUT}
          value={url}
          required
          placeholder={DEFAULT_PORT[kind]}
          aria-invalid={Boolean(fields.url)}
          onChange={(e) => setUrl(e.target.value)}
        />
        {fields.url && <span className="mt-1 block text-xs text-bad">{fields.url}</span>}
      </label>
      <label className="text-sm">
        {t('media.token')}
        <input
          className={INPUT}
          type="password"
          value={token}
          required
          autoComplete="off"
          onChange={(e) => setToken(e.target.value)}
        />
        <span className="mt-1 block text-xs text-muted">{t(`media.tokenHint.${kind}`)}</span>
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={BUTTON}
          disabled={!url || !token || test.isPending}
          onClick={() => test.mutate()}
        >
          {t('media.test')}
        </button>
        <button
          type="submit"
          disabled={!url || !token || save.isPending}
          className="rounded-control bg-accent px-3 py-1.5 text-sm font-bold text-on-accent"
        >
          {t('media.save')}
        </button>
        {test.data && (
          <span className="text-sm text-ok">
            {t('media.testOk', { version: test.data.version })}
          </span>
        )}
      </div>
      {(test.error || save.error) && (
        <p role="alert" className="text-sm text-bad">
          {errorText(t, test.error ?? save.error)}
        </p>
      )}
    </form>
  )
}

function ServerCard({ server }: { server: MediaServerView }) {
  const { t, i18n } = useTranslation()
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: ['media-servers'] })
  const select = useMutation({
    mutationFn: ({ id, selected }: { id: number; selected: boolean }) =>
      apiFetch(`/api/v1/media-servers/${server.id}/users/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ selected }),
      }),
    onSuccess: refresh,
  })
  const sync = useMutation({
    mutationFn: () => apiFetch(`/api/v1/media-servers/${server.id}/sync`, { method: 'POST' }),
  })
  const remove = useMutation({
    mutationFn: () => apiFetch(`/api/v1/media-servers/${server.id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  })
  return (
    <li className="flex flex-col gap-3 rounded-card border border-line p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p>
          <span className="font-bold">{server.name}</span>{' '}
          <span className="text-sm text-muted">
            {KIND_NAMES[server.kind]} · {server.url} ·{' '}
            <span className="font-mono">{server.token}</span>
          </span>
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            className={BUTTON}
            disabled={sync.isPending}
            onClick={() => sync.mutate()}
          >
            {t('media.syncNow')}
          </button>
          <button
            type="button"
            className={BUTTON}
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            {t('media.remove')}
          </button>
        </div>
      </div>
      <p className={`text-sm ${server.last_error ? 'text-bad' : 'text-muted'}`}>
        {server.last_error ??
          (server.last_sync_at
            ? t('media.lastSync', { time: formatDate(server.last_sync_at, i18n.language, true) })
            : t('media.neverSynced'))}
        {sync.isSuccess && ` ${t('media.syncQueued')}`}
      </p>
      <fieldset>
        <legend className="text-xs text-muted">{t('media.users')}</legend>
        {server.users.map((user) => (
          <Toggle
            key={user.id}
            label={user.name}
            hint={
              user.selected ? t('media.watchedCount', { count: user.watched_episodes }) : undefined
            }
            checked={user.selected}
            disabled={select.isPending}
            onChange={(selected) => select.mutate({ id: user.id, selected })}
          />
        ))}
      </fieldset>
      {server.unmatched.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted">
            {t('media.unmatched', { count: server.unmatched.length })}
          </summary>
          <p className="mt-1 text-xs text-muted">{t('media.unmatchedHint')}</p>
          <ul className="mt-1 columns-2 text-xs">
            {server.unmatched.map((title) => (
              <li key={title}>{title}</li>
            ))}
          </ul>
        </details>
      )}
    </li>
  )
}

function RuleForm() {
  const { t } = useTranslation()
  const client = useQueryClient()
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiFetch<RuleSettings>('/api/v1/settings'),
  })
  const save = useMutation({
    mutationFn: (change: Partial<RuleSettings>) =>
      apiFetch<RuleSettings>('/api/v1/settings', { method: 'PATCH', body: JSON.stringify(change) }),
    onSuccess: (data) => client.setQueryData(['settings'], data),
  })
  const s = settings.data
  if (!s) return null
  const number = (key: 'auto_follow_min_episodes' | 'auto_follow_days', max: number) => (
    <input
      type="number"
      min={1}
      max={max}
      defaultValue={s[key]}
      disabled={!s.auto_follow}
      onBlur={(e) => {
        const value = Number(e.target.value)
        if (value >= 1 && value <= max && value !== s[key]) save.mutate({ [key]: value })
      }}
      className="w-20 rounded-control border border-line bg-bg px-2 py-1 text-sm"
    />
  )
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 font-display font-semibold">{t('media.rule')}</legend>
      <Toggle
        label={t('media.ruleOn')}
        checked={s.auto_follow}
        disabled={save.isPending}
        onChange={(auto_follow) => save.mutate({ auto_follow })}
      />
      <label className="flex items-center gap-2 text-sm">
        {number('auto_follow_min_episodes', 50)} {t('media.ruleEpisodes')}
      </label>
      <label className="flex items-center gap-2 text-sm">
        {number('auto_follow_days', 365)} {t('media.ruleDays')}
      </label>
      {save.isError && <p className="text-sm text-bad">{errorText(t, save.error)}</p>}
    </fieldset>
  )
}

/** Emby, Jellyfin and Plex: whose viewing makes Finalarr follow a series. */
export function MediaServersSettings() {
  const { t } = useTranslation()
  const servers = useServers()
  const [adding, setAdding] = useState(false)
  return (
    <section className="flex flex-col gap-4 rounded-card border border-line bg-surface p-4">
      <p className="max-w-prose text-sm text-muted">{t('media.intro')}</p>
      {servers.isError && <p className="text-sm text-bad">{errorText(t, servers.error)}</p>}
      {servers.data?.length === 0 && !adding && <p className="text-sm">{t('media.empty')}</p>}
      <ul className="flex flex-col gap-3">
        {servers.data?.map((server) => (
          <ServerCard key={server.id} server={server} />
        ))}
      </ul>
      {adding ? (
        <AddServer onDone={() => setAdding(false)} />
      ) : (
        <button type="button" className={`${BUTTON} w-fit`} onClick={() => setAdding(true)}>
          {t('media.add')}
        </button>
      )}
      <RuleForm />
    </section>
  )
}
