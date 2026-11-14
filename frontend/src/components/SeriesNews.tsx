import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch, errorText } from '../lib/api'
import { type EventPayload, type EventType, formatEvent, type NewsKind } from '../lib/events'
import { formatDate } from '../lib/format'

type NewsItem =
  | { kind: 'event'; event_type: EventType; payload: EventPayload; published: string }
  | {
      kind: 'web'
      title: string
      news_kind?: NewsKind
      link: string | null
      source: string | null
      published: string | null
    }

interface News {
  items: NewsItem[]
  web_enabled: boolean
  web_error: boolean
}

function KindChip({ kind }: { kind: NewsKind | undefined }) {
  const { t } = useTranslation()
  if (!kind || kind === 'other') return null
  // Bad news in red, everything else quiet (gold stays reserved for "complete").
  const tone = kind === 'cancellation' || kind === 'delay' ? 'border-bad text-bad' : 'border-line'
  return (
    <span className={`mr-1.5 rounded-full border px-1.5 text-xs ${tone}`}>
      {t(`news.kinds.${kind}`)}
    </span>
  )
}

function ExternalLink({
  href,
  children,
}: {
  href: string | null | undefined
  children: React.ReactNode
}) {
  if (!href) return <span>{children}</span>
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" className="hover:text-accent">
      {children}
    </a>
  )
}

/** Latest news for one series: Finalarr's own announcements first, then web headlines. */
export function SeriesNews({ seriesId }: { seriesId: number }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language === 'en' ? 'en' : 'de'
  const news = useQuery({
    queryKey: ['series', 'news', seriesId, language],
    queryFn: () => apiFetch<News>(`/api/v1/series/${seriesId}/news?lang=${language}`),
    staleTime: 10 * 60_000,
  })
  return (
    <section
      className="mb-6 rounded-card border border-line bg-surface p-4"
      aria-labelledby="series-news"
    >
      <h2 id="series-news" className="mb-3 font-display font-semibold">
        {t('news.title')}
      </h2>
      {news.isError && <p className="text-sm text-bad">{errorText(t, news.error)}</p>}
      {news.data && news.data.items.length === 0 && (
        <p className="text-sm text-muted">{t('news.empty')}</p>
      )}
      <ul className="flex flex-col gap-2">
        {news.data?.items.map((item, index) => (
          <li key={index} className="flex flex-wrap items-baseline gap-x-3 text-sm">
            <span className="w-24 shrink-0 text-xs text-muted">
              {item.published ? formatDate(item.published, i18n.language) : ''}
            </span>
            <span className="min-w-0 flex-1">
              <KindChip kind={item.kind === 'event' ? item.payload.news_kind : item.news_kind} />
              {item.kind === 'event' ? (
                <ExternalLink
                  href={item.event_type === 'news_mention' ? item.payload.link : undefined}
                >
                  {formatEvent(t, item.event_type, item.payload, i18n.language)}
                </ExternalLink>
              ) : (
                <ExternalLink href={item.link}>{item.title}</ExternalLink>
              )}
              {item.kind === 'event' && item.payload.evidence && (
                <q className="mt-0.5 block text-xs text-muted">{item.payload.evidence}</q>
              )}
            </span>
            <span className="text-xs text-muted">
              {item.kind === 'event'
                ? t('news.fromFinalarr')
                : item.source && t('news.via', { source: item.source })}
            </span>
          </li>
        ))}
      </ul>
      {news.data && !news.data.web_enabled && (
        <p className="mt-3 text-xs text-muted">{t('news.webOff')}</p>
      )}
      {news.data?.web_error && <p className="mt-3 text-xs text-muted">{t('news.webError')}</p>}
    </section>
  )
}
