import { useTranslation } from 'react-i18next'
import { EmptyState, PageTitle } from '../components/EmptyState'

export function DashboardPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageTitle>{t('dashboard.title')}</PageTitle>
      <EmptyState title={t('dashboard.emptyTitle')}>{t('dashboard.emptyBody')}</EmptyState>
      <div className="mt-6 grid gap-4 min-[900px]:grid-cols-3">
        {(['airing', 'upcoming', 'recent'] as const).map((column) => (
          <section key={column} className="rounded-card border border-line p-4">
            <h2 className="text-sm font-medium text-muted">{t(`dashboard.${column}`)}</h2>
            <p className="mt-3 font-mono text-3xl font-extrabold">0</p>
          </section>
        ))}
      </div>
    </>
  )
}
