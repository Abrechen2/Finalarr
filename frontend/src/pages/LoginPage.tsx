import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { A2Credit } from '../components/A2Credit'
import { Logo } from '../components/Logo'
import { AUTH_QUERY_KEY } from '../lib/auth'
import { apiFetch, errorKey } from '../lib/api'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const login = useMutation({
    mutationFn: (key: string) =>
      apiFetch('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ api_key: key }) }),
    onSuccess: async () => {
      queryClient.setQueryData(AUTH_QUERY_KEY, { authenticated: true })
      await navigate('/', { replace: true })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    login.mutate(apiKey)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-card border border-line bg-surface p-6"
      >
        <div className="mb-6 flex items-center gap-3">
          <Logo size={40} />
          <h1 className="font-display text-2xl font-bold tracking-tight">{t('login.title')}</h1>
        </div>
        <p className="mb-4 text-sm text-muted">{t('login.intro')}</p>
        <label htmlFor="api-key" className="mb-1 block text-sm font-medium">
          {t('login.apiKey')}
        </label>
        <input
          id="api-key"
          type="password"
          autoComplete="current-password"
          required
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          className="mb-4 w-full rounded-card border border-line bg-bg px-3 py-2"
        />
        {login.isError && (
          <p role="alert" className="mb-4 text-sm text-bad">
            {t(errorKey(login.error))}
          </p>
        )}
        <button
          type="submit"
          disabled={login.isPending}
          className="w-full rounded-control bg-accent px-4 py-2 font-bold text-on-accent disabled:opacity-60"
        >
          {login.isPending ? t('login.busy') : t('login.submit')}
        </button>
      </form>
      <A2Credit />
    </div>
  )
}
