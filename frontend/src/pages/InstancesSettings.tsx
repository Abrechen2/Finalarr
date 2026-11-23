import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Toggle } from '../components/Toggle'
import { ApiError, apiFetch, errorText } from '../lib/api'
import { formatDate } from '../lib/format'
import { type InstanceView, useInstances } from '../lib/instances'

const input = 'mt-1 w-full rounded-card border border-line bg-bg px-2 py-1.5 text-sm'
const button =
  'rounded-card border border-line px-3 py-1.5 text-sm text-muted hover:text-ink disabled:opacity-60'

export function InstanceForm({
  onSaved,
  onCancel,
}: {
  onSaved: (i: InstanceView) => void
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const [name, setName] = useState('Sonarr')
  const [url, setUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const body = () => JSON.stringify({ name, url, api_key: apiKey })
  const test = useMutation({
    mutationFn: () =>
      apiFetch<{ version: string }>('/api/v1/instances/test', { method: 'POST', body: body() }),
  })
  const save = useMutation({
    mutationFn: () => apiFetch<InstanceView>('/api/v1/instances', { method: 'POST', body: body() }),
    onSuccess: async (instance) => {
      await client.invalidateQueries({ queryKey: ['instances'] })
      onSaved(instance)
    },
  })
  const fields = [test.error, save.error].reduce<Record<string, string>>(
    (acc, e) => (e instanceof ApiError ? { ...acc, ...e.fields } : acc),
    {},
  )

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate()
  }

  return (
    <form onSubmit={submit} className="mt-3 rounded-card border border-line p-4">
      <div className="grid gap-3 min-[600px]:grid-cols-3">
        <label className="text-sm">
          {t('instance.name')}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className={input}
          />
        </label>
        <label className="text-sm">
          {t('instance.url')}
          <input
            value={url}
            placeholder={t('instance.urlHint')}
            onChange={(e) => setUrl(e.target.value)}
            required
            aria-invalid={Boolean(fields.url)}
            className={input}
          />
          {fields.url && <span className="mt-1 block text-xs text-bad">{fields.url}</span>}
        </label>
        <label className="text-sm">
          {t('instance.apiKey')}
          <input
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            required
            className={input}
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={button}
          disabled={test.isPending}
          onClick={() => test.mutate()}
        >
          {t('instance.test')}
        </button>
        <button
          type="submit"
          disabled={save.isPending}
          className="rounded-control bg-accent px-3 py-1.5 text-sm font-bold text-on-accent"
        >
          {t('instance.save')}
        </button>
        {onCancel && (
          <button type="button" className={button} onClick={onCancel}>
            {t('channel.cancel')}
          </button>
        )}
        <span role="status" className="text-sm">
          {test.isSuccess && (
            <span className="text-ok">{t('instance.testOk', { version: test.data.version })}</span>
          )}
          {(test.isError || save.isError) && (
            <span className="text-bad">{errorText(t, save.error ?? test.error)}</span>
          )}
        </span>
      </div>
    </form>
  )
}

export function WebhookUrl({ path }: { path: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}${path}`
  return (
    <div className="mt-2">
      <p className="text-xs text-muted">{t('instance.webhook')}</p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-card border border-line bg-bg px-2 py-1 text-xs">
          {url}
        </code>
        <button
          type="button"
          className={button}
          onClick={() => {
            void navigator.clipboard?.writeText(url).then(() => setCopied(true))
          }}
        >
          {copied ? t('instance.copied') : t('instance.copy')}
        </button>
      </div>
      <p className="mt-1 text-xs text-muted">{t('instance.webhookHint')}</p>
    </div>
  )
}

function InstanceRow({ instance }: { instance: InstanceView }) {
  const { t, i18n } = useTranslation()
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: ['instances'] })
  const call = (path: string, method: string, body?: object) =>
    apiFetch(`/api/v1/instances/${instance.id}${path}`, {
      method,
      body: body && JSON.stringify(body),
    })
  const patch = useMutation({
    mutationFn: (enabled: boolean) => call('', 'PATCH', { enabled }),
    onSuccess: refresh,
  })
  const test = useMutation({
    mutationFn: () => call('/test', 'POST') as Promise<{ version: string }>,
  })
  const sync = useMutation({ mutationFn: () => call('/sync', 'POST') })
  const rotate = useMutation({
    mutationFn: () => call('/rotate-token', 'POST'),
    onSuccess: refresh,
  })
  const remove = useMutation({ mutationFn: () => call('', 'DELETE'), onSuccess: refresh })
  const failed = patch.error ?? sync.error ?? rotate.error ?? remove.error
  return (
    <li className="rounded-card border border-line p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{instance.name}</p>
          <p className="text-xs text-muted">
            {instance.url} · <span className="font-mono">{instance.api_key}</span>
          </p>
          <p className="text-xs text-muted">
            {instance.last_sync_at
              ? t('instance.lastSync', {
                  date: formatDate(instance.last_sync_at, i18n.language, true),
                })
              : t('instance.neverSynced')}
          </p>
          {instance.last_error && <p className="text-xs text-bad">{instance.last_error}</p>}
        </div>
        <Toggle
          label={t('instance.enabled')}
          checked={instance.enabled}
          onChange={(on) => patch.mutate(on)}
        />
      </div>
      <WebhookUrl path={instance.webhook_path} />
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={button} onClick={() => test.mutate()}>
          {t('instance.test')}
        </button>
        <button type="button" className={button} onClick={() => sync.mutate()}>
          {t('instance.sync')}
        </button>
        <button
          type="button"
          className={button}
          onClick={() => window.confirm(t('instance.rotateConfirm')) && rotate.mutate()}
        >
          {t('instance.rotate')}
        </button>
        <button
          type="button"
          className={button}
          onClick={() =>
            window.confirm(t('instance.deleteConfirm', { name: instance.name })) && remove.mutate()
          }
        >
          {t('instance.delete')}
        </button>
      </div>
      <p role="status" className="mt-1 text-xs">
        {test.isSuccess && (
          <span className="text-ok">{t('instance.testOk', { version: test.data.version })}</span>
        )}
        {test.isError && <span className="text-bad">{errorText(t, test.error)}</span>}
        {sync.isSuccess && <span className="text-ok">{t('instance.syncQueued')}</span>}
      </p>
      {failed && (
        <p role="alert" className="mt-1 text-xs text-bad">
          {errorText(t, failed)}
        </p>
      )}
    </li>
  )
}

export function InstancesSettings() {
  const { t } = useTranslation()
  const [adding, setAdding] = useState(false)
  const instances = useInstances()
  return (
    <section className="rounded-card border border-line bg-surface p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-medium">{t('instance.title')}</h2>
        {!adding && (
          <button type="button" className={button} onClick={() => setAdding(true)}>
            {t('instance.add')}
          </button>
        )}
      </div>
      {instances.isError && (
        <p role="alert" className="mt-3 text-sm text-bad">
          {errorText(t, instances.error)}
        </p>
      )}
      {instances.data?.length === 0 && !adding && (
        <p className="mt-3 text-sm text-muted">{t('instance.empty')}</p>
      )}
      <ul className="mt-3 flex flex-col gap-2">
        {instances.data?.map((i) => (
          <InstanceRow key={i.id} instance={i} />
        ))}
      </ul>
      {adding && (
        <InstanceForm onSaved={() => setAdding(false)} onCancel={() => setAdding(false)} />
      )}
    </section>
  )
}
