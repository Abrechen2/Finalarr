import { screen } from '@testing-library/react'
import i18n from '../i18n'
import { renderWithProviders } from '../test/render'
import { A2Credit } from './A2Credit'

afterEach(() => i18n.changeLanguage('de'))

test('German credit links to the German hub with the outlined wordmark', () => {
  renderWithProviders(<A2Credit />)
  const link = screen.getByRole('link', { name: /Ein Projekt von/ })
  expect(link).toHaveAttribute('href', 'https://www.abrechen2.de/')
  const logo = screen.getByRole('img', { name: 'abrechen2' })
  expect(logo).toHaveAttribute('viewBox', '60 40 820 120')
  expect(Number(logo.getAttribute('width'))).toBeGreaterThanOrEqual(120)
  expect(logo.querySelectorAll('path')).toHaveLength(3)
})

test('English credit links to the English hub', async () => {
  await i18n.changeLanguage('en')
  renderWithProviders(<A2Credit />)
  expect(screen.getByRole('link', { name: /A project by/ })).toHaveAttribute(
    'href',
    'https://www.abrechen2.de/en/',
  )
})
