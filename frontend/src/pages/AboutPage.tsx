import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { A2Credit } from '../components/A2Credit'
import { PageTitle } from '../components/EmptyState'
import { Logo } from '../components/Logo'
import { apiFetch } from '../lib/api'

export function AboutPage() {
  const { t } = useTranslation()
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<{ version: string }>('/health'),
  })
  return (
    <>
      <PageTitle>{t('about.title')}</PageTitle>
      <div className="rounded-card border border-line bg-surface p-6">
        <div className="mb-6 flex items-center gap-4">
          <Logo size={64} />
          <p className="max-w-prose text-muted">{t('brand.claim')}</p>
        </div>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted">{t('about.version')}</dt>
          <dd>{health.data?.version ?? '–'}</dd>
          <dt className="text-muted">{t('about.licence')}</dt>
          <dd>GPL-3.0</dd>
        </dl>
        <div className="mt-8 flex flex-col gap-2">
          <A2Credit />
        </div>
      </div>
    </>
  )
}
