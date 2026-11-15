import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch, errorKey } from '../lib/api'
import { type EventType, type EventPayload, formatEvent } from '../lib/events'

interface DryRun {
  state: string
  events: { type: EventType; payload: EventPayload }[]
}

/** "Jetzt prüfen": dry run on stored data, plus a real reload from Sonarr. */
export function SeasonCheck({ seasonId, title }: { seasonId: number; title: string }) {
  const { t, i18n } = useTranslation()
  const dryRun = useMutation({
    mutationFn: () =>
      apiFetch<DryRun>(`/api/v1/seasons/${seasonId}/evaluate?dry_run=true`, { method: 'POST' }),
  })
  const refresh = useMutation({
    mutationFn: () => apiFetch(`/api/v1/seasons/${seasonId}/evaluate`, { method: 'POST' }),
  })
  const button =
    'rounded-card border border-line px-3 py-1 text-xs text-muted hover:text-ink disabled:opacity-60'
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={button}
          disabled={dryRun.isPending}
          onClick={() => dryRun.mutate()}
        >
          {t('check.dryRun')}
        </button>
        <button
          type="button"
          className={button}
          disabled={refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          {t('check.refresh')}
        </button>
      </div>
      <div role="status" className="mt-2 text-sm">
        {dryRun.data &&
          (dryRun.data.events.length === 0 ? (
            <p className="text-muted">
              {t('check.nothing', { state: t(`state.${dryRun.data.state}`) })}
            </p>
          ) : (
            <>
              <p className="text-muted">{t('check.would')}</p>
              <ul className="list-inside list-disc">
                {dryRun.data.events.map((e) => (
                  <li key={e.type}>
                    {formatEvent(t, e.type, { title, ...e.payload }, i18n.language)}
                  </li>
                ))}
              </ul>
            </>
          ))}
        {refresh.isSuccess && <p className="text-ok">{t('check.refreshQueued')}</p>}
        {(dryRun.isError || refresh.isError) && (
          <p className="text-bad">{t(errorKey(dryRun.error ?? refresh.error))}</p>
        )}
      </div>
    </div>
  )
}
