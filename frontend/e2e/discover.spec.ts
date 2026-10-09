import { type Page, expect, test } from '@playwright/test'

/** Plan Phase 3 "done when": a tasting can be logged from a brewery page. */

async function signIn(page: Page, subject: string, name: string) {
  const become = await page.request.get(`/api/v1/fake-github/become?subject=${subject}&name=${encodeURIComponent(name)}`)
  expect(become.ok()).toBeTruthy()
  await page.goto('/sign-in')
  await page.getByRole('link', { name: 'Continue with GitHub' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toContainText(name)
}

test('find a brewery and log a tasting there', async ({ page }) => {
  await signIn(page, '1001', 'Octo Cat')
  // A beer to rate, created through the API the way the beers page would.
  const created = await page.request.post('/api/v1/beers', {
    data: { name: 'Giesinger Helles' },
    headers: { Origin: new URL(page.url()).origin },
  })
  expect(created.status()).toBe(201)
  await page.goto('/breweries')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Discover')
  await page.getByLabel('Search breweries').fill('Giesinger')
  await page.getByRole('link', { name: /Giesinger/ }).first().click()
  await expect(page).toHaveURL(/\/breweries\/[0-9a-f-]{36}$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Giesinger')
  await page.getByRole('link', { name: 'Log a tasting here' }).click()
  await expect(page).toHaveURL(/\/tastings\/new\?brewery=/)
  await expect(page.getByRole('main')).toContainText('Giesinger')

  await page.getByLabel('A commercial beer').check()
  await page.getByRole('combobox', { name: 'Beer', exact: true }).selectOption({ label: 'Giesinger Helles' })
  await page.getByLabel('4.5 out of 5', { exact: true }).check({ force: true })
  await page.getByRole('button', { name: 'Save tasting' }).click()
  await expect(page).toHaveURL(/\/tastings$/)
  await expect(page.getByRole('main')).toContainText('at Giesinger')
})
