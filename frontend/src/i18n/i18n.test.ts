import de from './de.json'
import en from './en.json'

function flatten(tree: object, prefix = ''): Record<string, string> {
  return Object.entries(tree).reduce<Record<string, string>>((acc, [key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return typeof value === 'object'
      ? { ...acc, ...flatten(value as object, path) }
      : { ...acc, [path]: String(value) }
  }, {})
}

test('every German key has an English twin and vice versa', () => {
  expect(Object.keys(flatten(en)).sort()).toEqual(Object.keys(flatten(de)).sort())
})

test('no translation is empty', () => {
  for (const [key, value] of Object.entries({ ...flatten(de), ...flatten(en) })) {
    expect(value.trim(), key).not.toBe('')
  }
})

test('German and English use the same placeholders', () => {
  const placeholders = (text: string) => [...text.matchAll(/{{\s*(\w+)/g)].map((m) => m[1]).sort()
  const english = flatten(en)
  for (const [key, value] of Object.entries(flatten(de))) {
    expect(placeholders(english[key]), key).toEqual(placeholders(value))
  }
})

test('the page language follows the UI language from the start', async () => {
  const { default: i18n } = await import('./index')
  expect(document.documentElement.lang).toBe(i18n.language)
})
