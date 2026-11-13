import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageTitle } from '../components/EmptyState'
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

export function SettingsPage() {
  const { t, i18n } = useTranslation()
  const [theme, setTheme] = useState<Theme>(storedTheme)

  return (
    <>
      <PageTitle>{t('settings.title')}</PageTitle>
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
      <p className="mt-6 text-sm text-muted">{t('settings.comingSoon')}</p>
    </>
  )
}
