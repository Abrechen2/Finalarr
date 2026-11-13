import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch, errorText } from '../lib/api'
import { formatDate } from '../lib/format'

interface SystemStatus {
  version: string
  db: string
  scheduler: { running: boolean; jobs: { id: string; next_run: string | null }[] }
}

export function SystemSettings() {
  const { t, i18n } = useTranslation()
  const status = useQuery({
    queryKey: ['system'],
    queryFn: () => apiFetch<SystemStatus>('/api/v1/system/status'),
  })
  const logs = useQuery({
    queryKey: ['system', 'logs'],
    queryFn: () => apiFetch<{ lines: string[] }>('/api/v1/system/logs?tail=200'),
  })
  if (status.isError)
    return (
      <p role="alert" className="text-sm text-bad">
        {errorText(t, status.error)}
      </p>
    )
  if (!status.data) return null
  const s = status.data
  return (
    <section className="rounded-card border border-line bg-surface p-6">
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted">{t('system.version')}</dt>
        <dd className="font-mono">{s.version}</dd>
        <dt className="text-muted">{t('system.database')}</dt>
        <dd>{s.db}</dd>
        <dt className="text-muted">{t('system.scheduler')}</dt>
        <dd>{s.scheduler.running ? t('system.running') : t('system.stopped')}</dd>
      </dl>
      {s.scheduler.jobs.length > 0 && (
        <table className="mt-4 text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="pr-6 font-normal">{t('system.job')}</th>
              <th className="font-normal">{t('system.nextRun')}</th>
            </tr>
          </thead>
          <tbody>
            {s.scheduler.jobs.map((job) => (
              <tr key={job.id}>
                <td className="pr-6 font-mono">{job.id}</td>
                <td>{job.next_run ? formatDate(job.next_run, i18n.language, true) : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-4 text-xs text-muted">{t('system.apiKeyHint')}</p>
      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-sm font-medium">{t('system.logs')}</h2>
        <button
          type="button"
          onClick={() => void logs.refetch()}
          className="rounded-card border border-line px-2 py-1 text-xs text-muted hover:text-ink"
        >
          {t('system.reload')}
        </button>
      </div>
      <pre className="mt-2 max-h-96 overflow-auto rounded-card border border-line bg-bg p-3 text-xs">
        {logs.data?.lines.join('\n')}
      </pre>
    </section>
  )
}
