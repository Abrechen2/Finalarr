import { Bell, BellOff } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function FollowToggle({
  followed,
  busy,
  onChange,
}: {
  followed: boolean
  busy?: boolean
  onChange: (next: boolean) => void
}) {
  const { t } = useTranslation()
  const Icon = followed ? BellOff : Bell
  return (
    <button
      type="button"
      aria-pressed={followed}
      disabled={busy}
      onClick={() => onChange(!followed)}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-card border px-3 py-1.5 text-sm disabled:opacity-60 ${
        followed ? 'border-line text-muted hover:text-ink' : 'border-accent text-accent'
      }`}
    >
      <Icon size={16} aria-hidden="true" />
      {followed ? t('action.unfollow') : t('action.follow')}
    </button>
  )
}
