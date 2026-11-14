import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Toggle } from '../components/Toggle'
import { apiFetch, errorText } from '../lib/api'

export interface SourceView {
  id: string
  name: string
  url: string
  terms_url: string
  core: boolean
  needs_key: boolean
  configured: boolean
  enabled: boolean
}

const BADGE = 'rounded-full border px-2 text-xs'

/** Every outside service Finalarr asks, what for, under which terms — and a switch. */
export function SourcesSettings() {
  const { t } = useTranslation()
  const client = useQueryClient()
  const sources = useQuery({
    queryKey: ['sources'],
    queryFn: () => apiFetch<SourceView[]>('/api/v1/sources'),
  })
  const patch = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      apiFetch<SourceView>(`/api/v1/sources/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['sources'] }),
  })
  return (
    <section className="rounded-card border border-line bg-surface p-4">
      <p className="mb-4 max-w-prose text-sm text-muted">{t('sources.intro')}</p>
      {sources.isError && <p className="text-sm text-bad">{errorText(t, sources.error)}</p>}
      {patch.isError && <p className="text-sm text-bad">{errorText(t, patch.error)}</p>}
      <ul className="flex flex-col divide-y divide-line">
        {sources.data?.map((source) => (
          <li key={source.id} className="flex flex-col gap-1 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={source.url}
                target="_blank"
                rel="noreferrer noopener"
                className="font-bold hover:text-accent"
              >
                {source.name}
              </a>
              {source.core && (
                <span className={`${BADGE} border-line`} title={t('sources.coreHint')}>
                  {t('sources.core')}
                </span>
              )}
              {source.needs_key && !source.configured && (
                <span
                  className={`${BADGE} border-line text-muted`}
                  title={t('sources.needsKeyHint')}
                >
                  {t('sources.needsKey')}
                </span>
              )}
            </div>
            <p className="text-sm">{t(`sources.items.${source.id}.use`)}</p>
            <p className="text-xs text-muted">
              {t(`sources.items.${source.id}.terms`)}{' '}
              <a
                href={source.terms_url}
                target="_blank"
                rel="noreferrer noopener"
                className="underline hover:text-accent"
              >
                {t('sources.terms')}
              </a>
            </p>
            <Toggle
              label={t('sources.toggle', { name: source.name })}
              hint={source.core && source.enabled ? t('sources.coreHint') : undefined}
              checked={source.enabled}
              disabled={patch.isPending || (source.needs_key && !source.configured)}
              onChange={(enabled) => patch.mutate({ id: source.id, enabled })}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}
