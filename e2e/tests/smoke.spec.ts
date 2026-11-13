import { expect, test } from '@playwright/test'

const SONARR = process.env.SONARR_URL ?? 'http://127.0.0.1:18990'
const KEY = process.env.FINALARR_API_KEY ?? ''

test('onboarding to a delivered report', async ({ page, request }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('API-Schlüssel').fill(KEY)
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.getByRole('heading', { name: 'Übersicht' })).toBeVisible()

  // Step 1: Sonarr
  await page.getByRole('link', { name: 'Einrichtung starten' }).click()
  await page.getByLabel('Sonarr-Adresse').fill(SONARR)
  await page.getByLabel('API-Schlüssel').fill('demo-key')
  await page.getByRole('button', { name: 'Verbindung testen' }).click()
  await expect(page.getByText('Verbunden mit Sonarr 4.0.99-fake.')).toBeVisible()
  await page.getByRole('button', { name: 'Speichern' }).click()
  await expect(page.getByText(/webhook\/sonarr\//)).toBeVisible()
  await page.getByRole('button', { name: 'Weiter' }).click()

  // Step 2: follow (the first sync runs right after the instance was added)
  await expect(async () => {
    await page.getByRole('button', { name: 'Alle überwachten folgen' }).click()
    await expect(page.getByText(/Du folgst [1-9]\d* Serien/)).toBeVisible({ timeout: 2_000 })
  }).toPass({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Weiter' }).click()

  // Step 3: a webhook channel pointing at the demo receiver
  await page.getByLabel('Dienst').selectOption('webhook')
  await page.getByRole('textbox', { name: 'URL', exact: true }).fill(`${SONARR}/_hooks`)
  await page.getByRole('button', { name: 'Testnachricht senden' }).click()
  await expect(page.getByText('Testnachricht verschickt.')).toBeVisible()
  await page.getByRole('button', { name: 'Speichern' }).click()
  await expect(page.getByRole('heading', { name: 'Übersicht' })).toBeVisible()

  // Wait until the followed series had their silent baseline, then add files.
  await expect(page.getByText('That Time I Got Reincarnated as a Slime').first()).toBeVisible({ timeout: 30_000 })
  await request.post(`${SONARR}/_control/files`, {
    data: { series: 1, season: 3, files: Array.from({ length: 20 }, (_, i) => i + 1) },
  })
  await page.goto('/settings')
  await page.getByRole('button', { name: 'Jetzt abgleichen' }).click()

  // The report shows up in the log and reaches the channel.
  await expect(async () => {
    await page.goto('/events')
    await expect(page.getByText(/S03 E19–E20 verfügbar \(20\/24\)/)).toBeVisible({ timeout: 2_000 })
  }).toPass({ timeout: 40_000 })
  await expect(async () => {
    const hooks = (await (await request.get(`${SONARR}/_hooks`)).json()) as { message: string }[]
    expect(hooks.some((h) => h.message.includes('S03 E19–E20 verfügbar (20/24)'))).toBe(true)
  }).toPass({ timeout: 30_000 })
  await page.reload()
  await expect(page.getByLabel(/Webhook: gesendet/)).toBeVisible()
})
