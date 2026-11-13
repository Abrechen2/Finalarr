import {
  CalendarCheck,
  CalendarDays,
  Info,
  LayoutDashboard,
  ListVideo,
  Settings,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'
import { A2Credit } from './A2Credit'
import { Logo } from './Logo'

const NAV = [
  { to: '/', key: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/series', key: 'nav.series', icon: ListVideo },
  { to: '/calendar', key: 'nav.calendar', icon: CalendarDays },
  { to: '/events', key: 'nav.events', icon: CalendarCheck },
  { to: '/settings', key: 'nav.settings', icon: Settings },
  { to: '/about', key: 'nav.about', icon: Info },
] as const

function linkClass({ isActive }: { isActive: boolean }) {
  const base =
    'flex flex-col items-center gap-1 px-2 text-xs min-[900px]:flex-row min-[900px]:gap-3 ' +
    'min-[900px]:rounded-card min-[900px]:px-3 min-[900px]:py-2 min-[900px]:text-sm'
  return isActive
    ? `${base} text-accent min-[900px]:bg-surface min-[900px]:text-ink`
    : `${base} text-muted hover:text-ink`
}

function Wordmark() {
  return (
    <span className="font-display text-lg font-bold tracking-tight">
      Final<span className="text-muted">arr</span>
    </span>
  )
}

/** Left rail from 900 px, bottom tabs below; the A2 credit sits in every footer. */
export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen min-[900px]:flex">
      <aside className="min-[900px]:flex min-[900px]:w-60 min-[900px]:shrink-0 min-[900px]:flex-col min-[900px]:border-r min-[900px]:border-line min-[900px]:p-4">
        <div className="mb-8 hidden items-center gap-3 px-1 min-[900px]:flex">
          <Logo />
          <Wordmark />
        </div>
        <nav
          aria-label={t('nav.label')}
          className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-line bg-bg py-2 min-[900px]:static min-[900px]:flex-col min-[900px]:justify-start min-[900px]:gap-1 min-[900px]:border-0 min-[900px]:bg-transparent min-[900px]:py-0"
        >
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/' || to === '/settings' || to === '/about'}
              className={linkClass}
            >
              <Icon size={18} aria-hidden="true" />
              {t(key)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-h-screen flex-1 flex-col pb-20 min-[900px]:pb-0">
        <header className="flex items-center gap-3 border-b border-line px-4 py-3 min-[900px]:hidden">
          <Logo size={28} />
          <Wordmark />
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 min-[900px]:px-8">
          {children}
        </main>
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-4 min-[900px]:px-8">
          <A2Credit />
        </footer>
      </div>
    </div>
  )
}
