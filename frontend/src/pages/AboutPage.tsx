import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { A2Credit } from '../components/A2Credit'
import { PageTitle } from '../components/EmptyState'
import { Logo } from '../components/Logo'
import tmdbLogo from '../assets/tmdb-logo.svg'
import { apiFetch } from '../lib/api'

const LINK = 'underline hover:text-accent'

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
        <section aria-labelledby="credits" className="mt-8 text-sm">
          <h2 id="credits" className="mb-1 font-display font-semibold">
            {t('about.credits')}
          </h2>
          <p className="mb-3 max-w-prose text-muted">{t('about.creditsIntro')}</p>
          <ul className="flex flex-col gap-1.5">
            <li>
              <a
                href="https://anilist.co"
                target="_blank"
                rel="noreferrer noopener"
                className={LINK}
              >
                AniList
              </a>
              {' · '}
              <a
                href="https://myanimelist.net"
                target="_blank"
                rel="noreferrer noopener"
                className={LINK}
              >
                MyAnimeList (Jikan)
              </a>
              {' · '}
              <a
                href="https://github.com/Fribb/anime-lists"
                target="_blank"
                rel="noreferrer noopener"
                className={LINK}
              >
                Fribb&apos;s anime-lists
              </a>
            </li>
            <li>
              <a
                href="https://www.tvmaze.com"
                target="_blank"
                rel="noreferrer noopener"
                className={LINK}
              >
                {t('about.tvmaze')}
              </a>
            </li>
            <li className="flex flex-wrap items-center gap-3">
              <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer noopener">
                <img src={tmdbLogo} alt="TMDB" className="h-3" />
              </a>
              <span className="text-muted">{t('about.tmdbNotice')}</span>
            </li>
            <li>
              <a
                href="https://www.justwatch.com"
                target="_blank"
                rel="noreferrer noopener"
                className={LINK}
              >
                {t('about.justwatch')}
              </a>
              {' · '}
              <a href="https://trakt.tv" target="_blank" rel="noreferrer noopener" className={LINK}>
                Trakt
              </a>
              {' · '}
              <a
                href="https://animeschedule.net"
                target="_blank"
                rel="noreferrer noopener"
                className={LINK}
              >
                AnimeSchedule.net
              </a>
            </li>
          </ul>
          <p className="mt-3">
            <a href="/licenses/INDEX.txt" target="_blank" rel="noreferrer" className={LINK}>
              {t('about.licences')}
            </a>
          </p>
        </section>
        <div className="mt-8 flex flex-col gap-2">
          <A2Credit />
        </div>
      </div>
    </>
  )
}
