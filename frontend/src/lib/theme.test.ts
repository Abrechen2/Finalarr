import { applyTheme, storedTheme } from './theme'

afterEach(() => {
  vi.restoreAllMocks()
  window.localStorage.clear()
})

test('defaults to the system theme', () => {
  expect(storedTheme()).toBe('system')
})

test('an explicit theme is applied and remembered', () => {
  applyTheme('light')
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(storedTheme()).toBe('light')
})

test('system removes the override', () => {
  applyTheme('dark')
  applyTheme('system')
  expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
})

test('an unknown stored value falls back to system', () => {
  window.localStorage.setItem('finalarr.theme', 'neon')
  expect(storedTheme()).toBe('system')
})

test('blocked storage never breaks the page', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(storedTheme()).toBe('system')
  expect(() => applyTheme('dark')).not.toThrow()
})
