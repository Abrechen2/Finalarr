import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { EmptyState } from '../components/EmptyState'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <EmptyState title={t('page.notFoundTitle')}>
      {t('page.notFound')}{' '}
      <Link to="/" className="text-accent underline">
        {t('page.home')}
      </Link>
    </EmptyState>
  )
}
