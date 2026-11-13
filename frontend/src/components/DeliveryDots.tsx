import { useTranslation } from 'react-i18next'
import type { DeliveryView } from '../lib/events'

const TONE = { pending: 'bg-warn', sent: 'bg-ok', failed: 'bg-bad' } as const

export function DeliveryDots({ deliveries }: { deliveries: DeliveryView[] }) {
  const { t } = useTranslation()
  if (deliveries.length === 0) {
    return <span className="text-xs text-muted">{t('events.noDelivery')}</span>
  }
  return (
    <ul className="flex gap-1.5">
      {deliveries.map((d) => {
        const label = `${d.channel_name}: ${t(`delivery.${d.status}`)}${d.last_error ? ` (${d.last_error})` : ''}`
        return (
          <li
            key={d.id}
            title={label}
            aria-label={label}
            className={`h-2.5 w-2.5 rounded-full ${TONE[d.status]}`}
          />
        )
      })}
    </ul>
  )
}
