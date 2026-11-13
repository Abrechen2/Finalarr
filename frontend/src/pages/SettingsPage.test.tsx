import { fireEvent, screen } from '@testing-library/react'
import i18n from '../i18n'
import { renderWithProviders } from '../test/render'
import { SettingsPage } from './SettingsPage'

afterEach(() => i18n.changeLanguage('de'))

test('switching to English translates the page', async () => {
  renderWithProviders(<SettingsPage />)
  fireEvent.click(screen.getByLabelText('English'))
  expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
})

test('choosing light sets the theme on the document', () => {
  renderWithProviders(<SettingsPage />)
  fireEvent.click(screen.getByLabelText('Hell'))
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(screen.getByLabelText('Hell')).toBeChecked()
})
