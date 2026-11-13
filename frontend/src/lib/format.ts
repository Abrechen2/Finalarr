export function formatDate(iso: string, language: string, withTime = false): string {
  const locale = language === 'en' ? 'en-GB' : 'de-DE'
  return new Date(iso).toLocaleString(
    locale,
    withTime ? { dateStyle: 'short', timeStyle: 'short' } : { dateStyle: 'medium' },
  )
}
