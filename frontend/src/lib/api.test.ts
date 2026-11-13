import { ApiError, apiFetch } from './api'
import { mockFetch } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

test('sends cookies and the CSRF header, returns JSON', async () => {
  const calls = mockFetch({ 'POST /api/v1/auth/logout': { body: { authenticated: false } } })
  await expect(apiFetch('/api/v1/auth/logout', { method: 'POST' })).resolves.toEqual({
    authenticated: false,
  })
  expect(calls[0].init?.credentials).toBe('same-origin')
  expect(new Headers(calls[0].init?.headers).get('X-Requested-With')).toBe('finalarr')
})

test('turns the API error body into an ApiError with code and status', async () => {
  mockFetch({
    'GET /api/v1/x': { status: 401, body: { error: { code: 'unauthorized', message: 'no' } } },
  })
  const error = await apiFetch('/api/v1/x').catch((e: unknown) => e)
  expect(error).toBeInstanceOf(ApiError)
  expect(error).toMatchObject({ status: 401, code: 'unauthorized' })
})

test('a non-JSON failure still becomes an ApiError', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response('boom', { status: 502 })),
  )
  await expect(apiFetch('/api/v1/x')).rejects.toMatchObject({ status: 502, code: 'http_502' })
})

test('error keys: known codes map to their text, the rest stays generic', async () => {
  const { ApiError: E, errorKey } = await import('./api')
  expect(errorKey(new E(401, 'unauthorized', ''))).toBe('error.unauthorized')
  expect(errorKey(new E(500, 'boom', ''))).toBe('error.generic')
  expect(errorKey(new TypeError('Failed to fetch'))).toBe('error.network')
})
