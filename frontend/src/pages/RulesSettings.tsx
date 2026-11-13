import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Toggle } from '../components/Toggle'
import { apiFetch, errorKey } from '../lib/api'

export interface GlobalRules {
  renotify_on_growth: boolean
  renotify_after_file_loss: boolean
  include_specials_default: boolean
  respect_monitoring_default: boolean
  stable_runs: number
  reconcile_interval_minutes: number
  news_feeds: boolean
}

const TOGGLES = [
  ['renotify_on_growth', 'renotifyOnGrowth', true],
  ['renotify_after_file_loss', 'renotifyAfterFileLoss', true],
  ['include_specials_default', 'includeSpecialsDefault', false],
  ['respect_monitoring_default', 'respectMonitoringDefault', false],
  ['news_feeds', 'newsFeeds', true],
] as const

const NUMBERS = [
  ['stable_runs', 'stableRuns', 1, 10],
  ['reconcile_interval_minutes', 'interval', 5, 1440],
] as const

export function RulesSettings() {
  const { t } = useTranslation()
  const client = useQueryClient()
  const rules = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiFetch<GlobalRules>('/api/v1/settings'),
  })
  const save = useMutation({
    mutationFn: (patch: Partial<GlobalRules>) =>
      apiFetch<GlobalRules>('/api/v1/settings', { method: 'PATCH', body: JSON.stringify(patch) }),
    onSuccess: (data) => client.setQueryData(['settings'], data),
  })

  if (rules.isError) {
    return (
      <p role="alert" className="text-sm text-bad">
        {t(errorKey(rules.error))}
      </p>
    )
  }
  if (!rules.data) return null
  const data = rules.data
  return (
    <section className="rounded-card border border-line bg-surface p-6">
      <h2 className="mb-4 font-medium">{t('rules.global')}</h2>
      {TOGGLES.map(([key, label, hasHint]) => (
        <Toggle
          key={key}
          label={t(`rules.${label}`)}
          hint={hasHint ? t(`rules.${label}Hint`) : undefined}
          checked={data[key]}
          disabled={save.isPending}
          onChange={(checked) => save.mutate({ [key]: checked })}
        />
      ))}
      <div className="mt-4 flex flex-wrap gap-6">
        {NUMBERS.map(([key, label, min, max]) => (
          <label key={key} className="flex flex-col text-sm">
            {t(`rules.${label}`)}
            <input
              type="number"
              min={min}
              max={max}
              defaultValue={data[key]}
              onBlur={(e) => {
                const value = Number(e.target.value)
                if (value !== data[key] && value >= min && value <= max)
                  save.mutate({ [key]: value })
              }}
              className="mt-1 w-24 rounded-card border border-line bg-bg px-2 py-1 font-mono"
            />
          </label>
        ))}
      </div>
      <p role="status" className="mt-3 text-xs">
        {save.isSuccess && <span className="text-ok">{t('rules.saved')}</span>}
        {save.isError && <span className="text-bad">{t(errorKey(save.error))}</span>}
      </p>
    </section>
  )
}
