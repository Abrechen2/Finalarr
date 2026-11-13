import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { DeliveryDots } from '../components/DeliveryDots'
import { EmptyState, PageTitle } from '../components/EmptyState'
import { apiFetch, errorKey } from '../lib/api'
import { EVENT_TYPES, type EventView, formatEvent, useEvents } from '../lib/events'

function ResendButton({ eventId }: { eventId: number }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const resend = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/events/${eventId}/resend`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['events'] }),
  })
  if (resend.isSuccess) return <span className="text-xs text-ok">{t('events.resent')}</span>
  return (
    <button
      type="button"
      onClick={() => resend.mutate()}
      disabled={resend.isPending}
      className="rounded-card border border-line px-2 py-0.5 text-xs text-muted hover:text-ink"
    >
      {t('events.resend')}
    </button>
  )
}

export function EventRow({ event, compact = false }: { event: EventView; compact?: boolean }) {
  const { t, i18n } = useTranslation()
  const when = new Date(event.created_at).toLocaleString(
    i18n.language === 'en' ? 'en-GB' : 'de-DE',
    {
      dateStyle: 'short',
      timeStyle: 'short',
    },
  )
  const text = formatEvent(t, event.type, event.payload, i18n.language)
  return (
    <li
      className={`flex flex-wrap gap-x-4 gap-y-1 ${
        compact ? 'flex-col' : 'items-center rounded-card border border-line bg-surface px-4 py-3'
      }`}
      title={t('event.fingerprint', { value: event.fingerprint })}
    >
      <span className={`${compact ? '' : 'w-28'} shrink-0 font-mono text-xs text-muted`}>
        {when}
        {compact && (
          <span className="ml-2 font-sans text-accent">{t(`event.types.${event.type}`)}</span>
        )}
      </span>
      {!compact && (
        <span className="w-28 shrink-0 text-xs text-accent">{t(`event.types.${event.type}`)}</span>
      )}
      <span className="min-w-0 flex-1 text-sm">
        {event.series_id ? (
          <Link to={`/series/${event.series_id}`} className="hover:text-accent">
            {text}
          </Link>
        ) : (
          text
        )}
      </span>
      <DeliveryDots deliveries={event.deliveries} />
      {!compact && <ResendButton eventId={event.id} />}
    </li>
  )
}

export function EventsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const type = params.get('type') ?? ''
  const q = params.get('q') ?? ''
  const events = useEvents(params.toString())
  const items = events.data?.pages.flatMap((p) => p.items) ?? []

  function update(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <PageTitle>{t('events.title')}</PageTitle>
      <div className="mb-4 flex flex-wrap gap-2">
        <input
          type="search"
          aria-label={t('events.search')}
          placeholder={t('events.search')}
          value={q}
          onChange={(e) => update('q', e.target.value)}
          className="min-w-56 flex-1 rounded-card border border-line bg-bg px-3 py-1.5 text-sm"
        />
        <select
          aria-label={t('events.filterType')}
          value={type}
          onChange={(e) => update('type', e.target.value)}
          className="rounded-card border border-line bg-bg px-3 py-1.5 text-sm"
        >
          <option value="">{t('events.allTypes')}</option>
          {EVENT_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`event.types.${value}`)}
            </option>
          ))}
        </select>
      </div>
      {events.isError && (
        <p role="alert" className="text-sm text-bad">
          {t(errorKey(events.error))}
        </p>
      )}
      {events.isSuccess &&
        items.length === 0 &&
        (type || q ? (
          <p className="text-sm text-muted">{t('events.noMatch')}</p>
        ) : (
          <EmptyState title={t('events.emptyTitle')}>{t('events.emptyBody')}</EmptyState>
        ))}
      <ul className="flex flex-col gap-2">
        {items.map((event) => (
          <EventRow key={event.id} event={event} />
        ))}
      </ul>
      {events.hasNextPage && (
        <button
          type="button"
          onClick={() => void events.fetchNextPage()}
          className="mt-4 rounded-card border border-line px-4 py-2 text-sm text-muted hover:text-ink"
        >
          {t('events.loadMore')}
        </button>
      )}
    </>
  )
}
