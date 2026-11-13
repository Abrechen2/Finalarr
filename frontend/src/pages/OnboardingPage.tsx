import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'
import { PageTitle } from '../components/EmptyState'
import { apiFetch } from '../lib/api'
import { useFollowMonitored } from '../lib/series'
import type { Page, SeriesSummary } from '../lib/types'
import { ChannelForm } from './ChannelsSettings'
import { type InstanceView, useInstances } from '../lib/instances'
import { InstanceForm, WebhookUrl } from './InstancesSettings'

const button = 'rounded-card border border-line px-3 py-1.5 text-sm text-muted hover:text-ink'

function StepSonarr({ onNext }: { onNext: () => void }) {
  const { t } = useTranslation()
  const instances = useInstances()
  const [created, setCreated] = useState<InstanceView | null>(null)
  const instance = created ?? instances.data?.[0] ?? null
  return (
    <>
      <p className="text-sm text-muted">{t('onboarding.s1Body')}</p>
      {instance ? (
        <div className="mt-3">
          <p className="text-sm">
            {instance.name} · {instance.url}
          </p>
          <WebhookUrl path={instance.webhook_path} />
        </div>
      ) : (
        <InstanceForm onSaved={setCreated} />
      )}
      <div className="mt-4 flex gap-2">
        <button type="button" className={button} onClick={onNext} disabled={!instance}>
          {t('onboarding.next')}
        </button>
      </div>
    </>
  )
}

function StepFollow({ onNext }: { onNext: () => void }) {
  const { t } = useTranslation()
  const followAll = useFollowMonitored()
  const followed = useQuery({
    queryKey: ['series', 'list', 'followed-count', followAll.data],
    queryFn: () => apiFetch<Page<SeriesSummary>>('/api/v1/series?followed=true&limit=200'),
  })
  const count = followed.data?.items.length ?? 0
  return (
    <>
      <p className="text-sm text-muted">{t('onboarding.s2Body')}</p>
      <p className="mt-3 text-sm">{t('onboarding.s2Count', { count })}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => followAll.mutate()}
          disabled={followAll.isPending}
          className="rounded-card bg-accent px-3 py-1.5 text-sm font-medium text-white"
        >
          {t('series.followAll')}
        </button>
        <Link to="/series" className={button}>
          {t('onboarding.s2Pick')}
        </Link>
        <button type="button" className={button} onClick={onNext}>
          {t('onboarding.next')}
        </button>
      </div>
    </>
  )
}

function StepChannel({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  return (
    <>
      <p className="text-sm text-muted">{t('onboarding.s3Body')}</p>
      <ChannelForm onDone={onDone} />
      <button type="button" className={`${button} mt-3`} onClick={onDone}>
        {t('onboarding.skip')}
      </button>
    </>
  )
}

export function OnboardingPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const titles = ['onboarding.s1Title', 'onboarding.s2Title', 'onboarding.s3Title']
  return (
    <>
      <PageTitle>{t('onboarding.title')}</PageTitle>
      <section className="rounded-card border border-line bg-surface p-6">
        <p className="text-xs text-muted">{t('onboarding.step', { n: step })}</p>
        <h2 className="mb-3 font-mono text-lg font-extrabold">{t(titles[step - 1])}</h2>
        {step === 1 && <StepSonarr onNext={() => setStep(2)} />}
        {step === 2 && <StepFollow onNext={() => setStep(3)} />}
        {step === 3 && <StepChannel onDone={() => void navigate('/')} />}
      </section>
    </>
  )
}
