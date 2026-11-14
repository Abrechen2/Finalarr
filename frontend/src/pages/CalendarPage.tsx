import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { PageTitle } from '../components/EmptyState'
import { errorText } from '../lib/api'
import {
  type CalendarEntry,
  dayKey,
  groupByDay,
  monthGrid,
  shiftMonth,
  useCalendar,
} from '../lib/calendar'
import { pad } from '../lib/episodes'

// Finale gold, premiere rose, the rest quiet (docs/DESIGN.md).
const TONE = {
  finale: 'border-gold text-gold',
  premiere: 'border-accent text-accent',
  episode: 'border-line text-ink',
  announcement: 'border-dashed border-muted text-muted',
} as const

function label(entry: CalendarEntry, t: (key: string) => string) {
  if (entry.kind === 'announcement') {
    return `${entry.title}: ${entry.sequel_title ?? `S${pad(entry.season)}`} (${t('calendar.kinds.announcement')})`
  }
  const code = `S${pad(entry.season)}E${pad(entry.episode ?? 0)}`
  const kind = entry.kind === 'episode' ? '' : ` · ${t(`calendar.kinds.${entry.kind}`)}`
  return `${entry.title} ${code}${kind}`
}

function Chip({ entry, locale }: { entry: CalendarEntry; locale: string }) {
  const { t } = useTranslation()
  const time = entry.all_day
    ? ''
    : new Date(entry.start).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
  const delayed = entry.delayed_from
    ? t('calendar.delayed', {
        date: new Date(entry.delayed_from).toLocaleDateString(locale, { dateStyle: 'medium' }),
      })
    : ''
  const text = label(entry, t) + (delayed ? ` (${delayed})` : '')
  const what =
    entry.kind === 'announcement'
      ? t('calendar.kinds.announcement')
      : [
          `S${pad(entry.season)}E${pad(entry.episode ?? 0)}`,
          entry.kind !== 'episode' && t(`calendar.kinds.${entry.kind}`),
        ]
          .filter(Boolean)
          .join(' · ')
  const body = (
    <span
      className={`block rounded-control border px-1.5 py-0.5 text-xs ${TONE[entry.kind]}${
        entry.has_file ? ' opacity-50' : ''
      }`}
      title={`${time ? `${time} ` : ''}${text}${entry.has_file ? ` (${t('calendar.onDisk')})` : ''}`}
    >
      <span className="block truncate font-bold">
        {time && <span className="mr-1 font-normal text-muted">{time}</span>}
        {what}
        {delayed && <span className="ml-1 font-normal text-sky">⏸</span>}
      </span>
      <span className="block truncate text-ink">{entry.title}</span>
    </span>
  )
  return entry.series_id ? (
    <Link to={`/series/${entry.series_id}`} aria-label={text}>
      {body}
    </Link>
  ) : (
    body
  )
}

export function CalendarPage() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'en' ? 'en-GB' : 'de-DE'
  const now = new Date()
  const [[year, month], setMonth] = useState<[number, number]>([now.getFullYear(), now.getMonth()])
  const days = monthGrid(year, month)
  const calendar = useCalendar(dayKey(days[0]), dayKey(days[days.length - 1]))
  const byDay = groupByDay(calendar.data?.entries ?? [])
  const today = dayKey(now)
  const monthDays = days.filter((d) => d.getMonth() === month)
  const title = new Date(year, month, 1).toLocaleDateString(locale, {
    month: 'long',
    year: 'numeric',
  })
  const button = 'rounded-control border border-line p-1.5 text-muted hover:text-ink'

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <PageTitle>{t('calendar.title')}</PageTitle>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label={t('calendar.previous')}
            className={button}
            onClick={() => setMonth(shiftMonth(year, month, -1))}
          >
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
          <span className="min-w-36 text-center font-bold" aria-live="polite">
            {title}
          </span>
          <button
            type="button"
            aria-label={t('calendar.next')}
            className={button}
            onClick={() => setMonth(shiftMonth(year, month, 1))}
          >
            <ChevronRight size={18} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`${button} px-3 text-sm`}
            onClick={() => setMonth([now.getFullYear(), now.getMonth()])}
          >
            {t('calendar.today')}
          </button>
        </div>
      </div>
      {calendar.isError && (
        <p role="alert" className="text-sm text-bad">
          {errorText(t, calendar.error)}
        </p>
      )}
      <div className="hidden min-[900px]:block">
        <div className="grid grid-cols-7 gap-px overflow-hidden rounded-card border border-line bg-line">
          {t('calendar.weekdays')
            .split(',')
            .map((name) => (
              <div key={name} className="bg-surface px-2 py-1 text-xs text-muted">
                {name}
              </div>
            ))}
          {days.map((day) => {
            const key = dayKey(day)
            const inMonth = day.getMonth() === month
            return (
              <div key={key} className={`min-h-28 bg-bg p-1.5 ${inMonth ? '' : 'opacity-40'}`}>
                <div
                  className={`mb-1 text-xs ${key === today ? 'inline-block rounded-full bg-accent px-1.5 font-bold text-on-accent' : 'text-muted'}`}
                >
                  {day.getDate()}
                </div>
                <ul className="flex flex-col gap-1">
                  {(byDay[key] ?? []).map((entry) => (
                    <li key={entry.uid}>
                      <Chip entry={entry} locale={locale} />
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </div>
      <ol className="flex flex-col gap-3 min-[900px]:hidden" aria-label={title}>
        {monthDays
          .filter((day) => byDay[dayKey(day)])
          .map((day) => (
            <li key={dayKey(day)}>
              <h2 className="mb-1 text-sm font-bold">
                {day.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long' })}
              </h2>
              <ul className="flex flex-col gap-1">
                {byDay[dayKey(day)].map((entry) => (
                  <li key={entry.uid}>
                    <Chip entry={entry} locale={locale} />
                  </li>
                ))}
              </ul>
            </li>
          ))}
      </ol>
      {calendar.isSuccess && monthDays.every((day) => !byDay[dayKey(day)]) && (
        <p className="mt-4 text-sm text-muted">{t('calendar.empty')}</p>
      )}
    </>
  )
}
