import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Circle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { PageTitle } from '../components/EmptyState'
import { SeasonProgress } from '../components/SeasonProgress'
import { apiFetch, errorText } from '../lib/api'
import { pad } from '../lib/episodes'
import type { EventView } from '../lib/events'
import { airTime, formatDate, relativeTime } from '../lib/format'
import type { SeasonState } from '../lib/types'
import { EventRow } from './EventsPage'

interface Card {
  series_id: number
  season_id: number
  title: string
  season: number
  state: SeasonState
  have: number
  expected: number | null
  disputed: boolean
  next_air_date: string | null
  next_episode: number | null
}

export interface Dashboard {
  airing: Card[]
  upcoming_finales: (Card & { episode: number; air_date: string })[]
  recent_events: EventView[]
  onboarding: { instance: boolean; followed: boolean; channel: boolean }
}

function Column({
  title,
  empty,
  children,
}: {
  title: string
  empty: string
  children: React.ReactNode[]
}) {
  return (
    <section className="rounded-card border border-line p-4">
      <h2 className="mb-3 text-sm font-medium text-muted">{title}</h2>
      {children.length ? (
        <ul className="flex flex-col gap-3">{children}</ul>
      ) : (
        <p className="text-sm text-muted">{empty}</p>
      )}
    </section>
  )
}

function Setup({ steps }: { steps: Dashboard['onboarding'] }) {
  const { t } = useTranslation()
  return (
    <section className="mb-6 rounded-card border border-accent bg-surface p-4">
      <h2 className="font-medium">{t('dashboard.setupTitle')}</h2>
      <ul className="mt-2 flex flex-col gap-1 text-sm">
        {(['instance', 'followed', 'channel'] as const).map((key) => (
          <li key={key} className="flex items-center gap-2">
            {steps[key] ? (
              <CheckCircle2 size={16} className="text-ok" aria-label={t('setup.done')} />
            ) : (
              <Circle size={16} className="text-muted" aria-label={t('setup.open')} />
            )}
            {t(`setup.${key}`)}
          </li>
        ))}
      </ul>
      <Link
        to="/onboarding"
        className="mt-3 inline-block rounded-control bg-accent px-3 py-1.5 text-sm font-bold text-on-accent"
      >
        {t('dashboard.setupStart')}
      </Link>
    </section>
  )
}

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const data = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<Dashboard>('/api/v1/dashboard'),
    refetchInterval: 60_000,
  })
  if (data.isError)
    return (
      <p role="alert" className="text-sm text-bad">
        {errorText(t, data.error)}
      </p>
    )
  if (!data.data) return null
  const d = data.data
  const incomplete = !d.onboarding.instance || !d.onboarding.followed || !d.onboarding.channel
  return (
    <>
      <PageTitle>{t('dashboard.title')}</PageTitle>
      {incomplete && <Setup steps={d.onboarding} />}
      <div className="grid gap-4 min-[1100px]:grid-cols-3">
        <Column title={t('dashboard.airing')} empty={t('dashboard.nothingAiring')}>
          {d.airing.map((c) => (
            <li key={c.season_id}>
              <Link to={`/series/${c.series_id}`} className="text-sm font-medium hover:text-accent">
                {c.title}
              </Link>
              <SeasonProgress
                season={{
                  id: c.season_id,
                  number: c.season,
                  state: c.state,
                  expected: c.expected,
                  have: c.have,
                  disputed: c.disputed,
                }}
              />
              {c.next_air_date && (
                <p className="text-xs text-muted">
                  {typeof c.next_episode === 'number'
                    ? t('dashboard.nextEpisode', {
                        e: c.next_episode,
                        relative: relativeTime(c.next_air_date, i18n.language),
                        when: airTime(c.next_air_date, i18n.language),
                      })
                    : t('dashboard.nextAir', {
                        date: formatDate(c.next_air_date, i18n.language),
                      })}
                </p>
              )}
            </li>
          ))}
        </Column>
        <Column title={t('dashboard.upcoming')} empty={t('dashboard.noFinales')}>
          {d.upcoming_finales.map((f) => (
            <li key={f.season_id}>
              <Link to={`/series/${f.series_id}`} className="text-sm font-medium hover:text-accent">
                {f.title}
              </Link>
              <p className="text-xs text-muted">
                {t('dashboard.finaleOn', {
                  s: pad(f.season),
                  e: pad(f.episode),
                  date: formatDate(f.air_date, i18n.language),
                })}
              </p>
            </li>
          ))}
        </Column>
        <Column title={t('dashboard.recent')} empty={t('dashboard.noEvents')}>
          {d.recent_events.map((e) => (
            <EventRow key={e.id} event={e} compact />
          ))}
        </Column>
      </div>
    </>
  )
}
