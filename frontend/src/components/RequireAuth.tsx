import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import { useAuthStatus } from '../lib/auth'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { data, isPending } = useAuthStatus()
  if (isPending) return null
  if (!data?.authenticated) return <Navigate to="/login" replace />
  return children
}
