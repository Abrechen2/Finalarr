export const CSRF_HEADER = { 'X-Requested-With': 'finalarr' }

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/** Fetch JSON from the Finalarr API with the session cookie and the CSRF header. */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  Object.entries(CSRF_HEADER).forEach(([key, value]) => headers.set(key, value))
  if (init.body) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error
    throw new ApiError(
      response.status,
      error?.code ?? `http_${response.status}`,
      error?.message ?? response.statusText,
    )
  }
  return body as T
}

/** i18n key for an error shown to the user; detail stays in the server log. */
export function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    return ['unauthorized', 'rate_limited'].includes(error.code)
      ? `error.${error.code}`
      : 'error.generic'
  }
  return 'error.network'
}
