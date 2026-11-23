import { Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { RequireAuth } from './components/RequireAuth'
import { AboutPage } from './pages/AboutPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { EventsPage } from './pages/EventsPage'
import { CalendarPage } from './pages/CalendarPage'
import { DashboardPage } from './pages/DashboardPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { SeriesDetailPage } from './pages/SeriesDetailPage'
import { SeriesPage } from './pages/SeriesPage'
import { SettingsPage } from './pages/SettingsPage'
import { WatchTrackerPage } from './pages/WatchTrackerPage'

const PAGES = [
  { path: '/', element: <DashboardPage /> },
  { path: '/series', element: <SeriesPage /> },
  { path: '/series/:id', element: <SeriesDetailPage /> },
  { path: '/watch', element: <WatchTrackerPage /> },
  { path: '/calendar', element: <CalendarPage /> },
  { path: '/events', element: <EventsPage /> },
  { path: '/settings', element: <SettingsPage /> },
  { path: '/about', element: <AboutPage /> },
  { path: '/onboarding', element: <OnboardingPage /> },
  { path: '*', element: <NotFoundPage /> },
]

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {PAGES.map(({ path, element }) => (
        <Route
          key={path}
          path={path}
          element={
            <RequireAuth>
              <AppShell>{element}</AppShell>
            </RequireAuth>
          }
        />
      ))}
    </Routes>
  )
}
