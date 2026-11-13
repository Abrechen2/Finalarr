import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Toggle } from '../components/Toggle'
import { apiFetch, errorText } from '../lib/api'
import type { GlobalRules } from './RulesSettings'

const SCOPES = [
  ['finales', 'scopeFinales'],
  ['milestones', 'scopeMilestones'],
  ['all', 'scopeAll'],
] as const

interface Feed {
  enabled: boolean
  path: string | null
  /** Public address (FINALARR_FEED_URL) when Finalarr's feed is reachable from outside. */
  url: string | null
}

const button = 'rounded-control border border-line px-3 py-1.5 text-sm text-muted hover:text-ink'

function FeedPanel() {
  const { t, i18n } = useTranslation()
  const client = useQueryClient()
  const [copied, setCopied] = useState(false)
  const feed = useQuery({
    queryKey: ['calendar-feed'],
    queryFn: () => apiFetch<Feed>('/api/v1/calendar/feed'),
  })
  const update = (data: Feed) => client.setQueryData(['calendar-feed'], data)
  const toggle = useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch<Feed>('/api/v1/calendar/feed', { method: 'PUT', body: JSON.stringify({ enabled }) }),
    onSuccess: update,
  })
  const rotate = useMutation({
    mutationFn: () => apiFetch<Feed>('/api/v1/calendar/feed/rotate', { method: 'POST' }),
    onSuccess: update,
  })
  const url = feed.data?.path
    ? `${window.location.origin}${feed.data.path}?lang=${i18n.language}`
    : null
  return (
    <section className="mt-4 rounded-card border border-line bg-surface p-6">
      <h2 className="mb-2 font-medium">{t('calendar.feed')}</h2>
      <Toggle
        label={t('calendar.feedOn')}
        checked={Boolean(feed.data?.enabled)}
        disabled={toggle.isPending || !feed.data}
        onChange={(on) => toggle.mutate(on)}
      />
      {url && (
        <>
          <code className="mt-2 block truncate rounded-control border border-line bg-bg px-2 py-1 text-xs">
            {url}
          </code>
          <p className="mt-2 max-w-prose text-xs text-muted">{t('calendar.feedHint')}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              onClick={() => void navigator.clipboard?.writeText(url).then(() => setCopied(true))}
            >
              {copied ? t('calendar.copied') : t('calendar.copy')}
            </button>
            <button
              type="button"
              className={button}
              onClick={() => window.confirm(t('calendar.rotateConfirm')) && rotate.mutate()}
            >
              {t('calendar.rotate')}
            </button>
          </div>
        </>
      )}
      {(feed.isError || toggle.isError) && (
        <p role="alert" className="mt-2 text-sm text-bad">
          {errorText(t, feed.error ?? toggle.error)}
        </p>
      )}
    </section>
  )
}

export function CalendarSettings() {
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
  const data = rules.data
  return (
    <>
      {data && (
        <section className="rounded-card border border-line bg-surface p-6">
          <fieldset>
            <legend className="mb-1 text-sm font-medium">{t('calendar.scope')}</legend>
            <p className="mb-2 text-xs text-muted">{t('calendar.scopeHint')}</p>
            {SCOPES.map(([value, key]) => (
              <label key={value} className="flex items-center gap-2 py-1 text-sm">
                <input
                  type="radio"
                  name="calendar-scope"
                  checked={data.calendar_scope === value}
                  onChange={() => save.mutate({ calendar_scope: value })}
                  className="accent-[var(--accent)]"
                />
                {t(`calendar.${key}`)}
              </label>
            ))}
          </fieldset>
          <div className="mt-3">
            <Toggle
              label={t('calendar.hideDownloaded')}
              checked={data.calendar_hide_downloaded}
              onChange={(v) => save.mutate({ calendar_hide_downloaded: v })}
            />
            <Toggle
              label={t('calendar.announcements')}
              checked={data.calendar_announcements}
              onChange={(v) => save.mutate({ calendar_announcements: v })}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-6">
            {(
              [
                ['calendar_days_back', 'daysBack', 0, 90],
                ['calendar_days_ahead', 'daysAhead', 7, 730],
              ] as const
            ).map(([field, key, min, max]) => (
              <label key={field} className="flex flex-col text-sm">
                {t(`calendar.${key}`)}
                <input
                  type="number"
                  min={min}
                  max={max}
                  defaultValue={data[field]}
                  onBlur={(e) => {
                    const value = Number(e.target.value)
                    if (value !== data[field] && value >= min && value <= max)
                      save.mutate({ [field]: value })
                  }}
                  className="mt-1 w-24 rounded-control border border-line bg-bg px-2 py-1"
                />
              </label>
            ))}
          </div>
          <p role="status" className="mt-2 text-xs">
            {save.isSuccess && <span className="text-ok">{t('rules.saved')}</span>}
            {save.isError && <span className="text-bad">{errorText(t, save.error)}</span>}
          </p>
        </section>
      )}
      <FeedPanel />
    </>
  )
}
