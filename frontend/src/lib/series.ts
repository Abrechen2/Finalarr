import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './api'
import type { Page, SeriesDetail, SeriesSummary } from './types'

export interface SeriesFilter {
  q: string
  followed: '' | 'true' | 'false'
  type: '' | 'anime' | 'standard'
}

export function seriesQueryString(filter: SeriesFilter, cursor?: string | null): string {
  const params = new URLSearchParams()
  if (filter.q.trim()) params.set('q', filter.q.trim())
  if (filter.followed) params.set('followed', filter.followed)
  if (filter.type) params.set('type', filter.type)
  if (cursor) params.set('cursor', cursor)
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function useSeriesList(filter: SeriesFilter) {
  return useInfiniteQuery({
    queryKey: ['series', 'list', filter],
    queryFn: ({ pageParam }) =>
      apiFetch<Page<SeriesSummary>>(`/api/v1/series${seriesQueryString(filter, pageParam)}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useSeriesDetail(id: number) {
  return useQuery({
    queryKey: ['series', 'detail', id],
    queryFn: () => apiFetch<SeriesDetail>(`/api/v1/series/${id}`),
  })
}

export function useSeriesPatch() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Partial<SeriesSummary>) =>
      apiFetch<SeriesDetail>(`/api/v1/series/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: (detail) => {
      client.setQueryData(['series', 'detail', detail.id], detail)
      return client.invalidateQueries({ queryKey: ['series', 'list'] })
    },
  })
}

export function useFollowMonitored() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<{ followed: number }>('/api/v1/series/follow-monitored', {
        method: 'POST',
        body: JSON.stringify({}),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['series'] }),
  })
}
