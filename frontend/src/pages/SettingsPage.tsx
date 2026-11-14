import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageTitle } from '../components/EmptyState'
import { CalendarSettings } from './CalendarSettings'
import { ChannelsSettings } from './ChannelsSettings'
import { InstancesSettings } from './InstancesSettings'
import { SystemSettings } from './SystemSettings'
import { RulesSettings } from './RulesSettings'
import { SourcesSettings } from './SourcesSettings'
import { LANGUAGES } from '../i18n'
import { THEMES, type Theme, applyTheme, storedTheme } from '../lib/theme'

const THEME_LABEL = { system: 'themeSystem', dark: 'themeDark', light: 'themeLight' } as const

function Choice<T extends string>(props: {
  legend: string
  name: string
  options: readonly T[]
  value: T
  label: (option: T) => string
  onChange: (option: T) => void
}) {
  return (
    <fieldset className="mb-6">
      <legend className="mb-2 text-sm font-medium">{props.legend}</legend>
      <div className="flex flex-wrap gap-2">
        {props.options.map((option) => (
          <label
            key={option}
            className={`cursor-pointer rounded-card border px-3 py-1.5 text-sm ${
              props.value === option ? 'border-accent text-ink' : 'border-line text-muted'
            }`}
          >
            <input
              type="radio"
              name={props.name}
              value={option}
              checked={props.value === option}
              onChange={() => props.onChange(option)}
              className="sr-only"
            />
            {props.label(option)}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

const TABS = ['sonarr', 'channels', 'rules', 'calendar', 'sources', 'appearance', 'system'] as const
type Tab = (typeof TABS)[number]
const TAB_LABEL = {
  sonarr: 'settings.tabSonarr',
  channels: 'settings.tabChannels',
  rules: 'settings.tabRules',
  calendar: 'settings.tabCalendar',
  sources: 'settings.tabSources',
  appearance: 'settings.tabAppearance',
  system: 'settings.tabSystem',
} as const
const PANELS = {
  sonarr: InstancesSettings,
  channels: ChannelsSettings,
  rules: RulesSettings,
  calendar: CalendarSettings,
  sources: SourcesSettings,
  appearance: AppearanceSettings,
  system: SystemSettings,
}

export function SettingsPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('sonarr')
  const Panel = PANELS[tab]
  return (
    <>
      <PageTitle>{t('settings.title')}</PageTitle>
      <div role="tablist" className="mb-4 flex gap-1 border-b border-line">
        {TABS.map((value) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === value
                ? 'border-accent text-ink'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {t(TAB_LABEL[value])}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        <Panel />
      </div>
    </>
  )
}

function AppearanceSettings() {
  const { t, i18n } = useTranslation()
  const [theme, setTheme] = useState<Theme>(storedTheme)

  return (
    <>
      <section className="rounded-card border border-line bg-surface p-6">
        <h2 className="mb-4 font-medium">{t('settings.appearance')}</h2>
        <Choice
          legend={t('settings.theme')}
          name="theme"
          options={THEMES}
          value={theme}
          label={(option) => t(`settings.${THEME_LABEL[option]}`)}
          onChange={(option) => {
            applyTheme(option)
            setTheme(option)
          }}
        />
        <Choice
          legend={t('settings.language')}
          name="language"
          options={LANGUAGES}
          value={i18n.language === 'en' ? 'en' : 'de'}
          label={(option) => (option === 'de' ? 'Deutsch' : 'English')}
          onChange={(option) => void i18n.changeLanguage(option)}
        />
      </section>
    </>
  )
}
