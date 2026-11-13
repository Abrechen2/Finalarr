import { initialLanguage } from './detect'

test.each([
  [null, 'de-DE', 'de'],
  [null, 'de-AT', 'de'],
  [null, 'en-US', 'en'],
  [null, 'fr-FR', 'en'],
  ['de', 'en-US', 'de'],
  ['en', 'de-DE', 'en'],
  ['xx', 'de-DE', 'de'],
])('stored %s, browser %s → %s', (stored, browser, expected) => {
  expect(initialLanguage(stored, browser)).toBe(expected)
})
