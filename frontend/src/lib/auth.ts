import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './api'

export const AUTH_QUERY_KEY = ['auth', 'status']

export function useAuthStatus() {
  return useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: () => apiFetch<{ authenticated: boolean }>('/api/v1/auth/status'),
  })
}
