import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './api'

export interface InstanceView {
  id: number
  name: string
  url: string
  api_key: string
  enabled: boolean
  webhook_path: string
  last_sync_at: string | null
  last_error: string | null
}

export function useInstances() {
  return useQuery({
    queryKey: ['instances'],
    queryFn: () => apiFetch<InstanceView[]>('/api/v1/instances'),
  })
}
