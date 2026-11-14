export function formatDate(iso: string, language: string, withTime = false): string {
  const locale = language === 'en' ? 'en-GB' : 'de-DE'
  return new Date(iso).toLocaleString(
    locale,
    withTime ? { dateStyle: 'short', timeStyle: 'short' } : { dateStyle: 'medium' },
  )
}

const DAY = 86_400_000
// [unit, length, used from]: days up to two months, then months, then years.
const UNITS: [Intl.RelativeTimeFormatUnit, number, number][] = [
  ['year', 365 * DAY, 365 * DAY],
  ['month', 30 * DAY, 60 * DAY],
  ['day', DAY, DAY],
  ['hour', 3_600_000, 3_600_000],
  ['minute', 60_000, 0],
]

/** "in 3 Tagen", "morgen", "in 5 Stunden" — the countdown to an air time. */
export function relativeTime(iso: string, language: string, now = new Date()): string {
  const diff = new Date(iso).getTime() - now.getTime()
  const format = new Intl.RelativeTimeFormat(language === 'en' ? 'en' : 'de', { numeric: 'auto' })
  const [unit, size] = UNITS.find(([, , from]) => Math.abs(diff) >= from) ?? UNITS[UNITS.length - 1]
  return format.format(Math.round(diff / size), unit)
}

/** Weekday, date and time, e.g. "Sa., 21.11., 17:00". */
export function airTime(iso: string, language: string): string {
  return new Date(iso).toLocaleString(language === 'en' ? 'en-GB' : 'de-DE', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
