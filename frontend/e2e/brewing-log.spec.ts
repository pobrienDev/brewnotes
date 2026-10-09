import { type Page, expect, test } from '@playwright/test'

/**
 * The plan's smoke tests: build, save and reload a recipe; log a batch. Each test signs in
 * through the real sign-in flow against the fake GitHub in the harness.
 */

test.describe.configure({ mode: 'serial' })

const RECIPE_NAME = `E2E Pale Ale ${Date.now()}`
const BATCH_NAME = `E2E batch ${Date.now()}`
let batchUrl = ''

async function signIn(page: Page, subject: string, name: string) {
  const become = await page.request.get(`/api/v1/fake-github/become?subject=${subject}&name=${encodeURIComponent(name)}`)
  expect(become.ok()).toBeTruthy()
  await page.goto('/sign-in')
  await page.getByRole('link', { name: 'Continue with GitHub' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toContainText(name)
}

function row(page: Page, label: string) {
  return page.getByRole('row').filter({ has: page.getByLabel(label) })
}

test('build, save and reload a recipe', async ({ page }) => {
  await signIn(page, '1001', 'Octo Cat')
  await page.goto('/recipes/new')
  await page.getByLabel('Name', { exact: true }).fill(RECIPE_NAME)
  await page.getByLabel('Target style').selectOption({ label: '18B American Pale Ale' })
  await page.getByLabel(/^Batch volume/).fill('5.5')
  await page.getByLabel('Boil time (min)').fill('60')

  if ((await page.getByLabel('Fermentable 1 name').count()) === 0) {
    await page.getByRole('button', { name: 'Add fermentable' }).click()
  }
  await page.getByLabel('Fermentable 1 name').fill('2-row')
  await page.getByRole('listbox').getByRole('button', { name: /2-row/i }).first().click()
  await row(page, 'Fermentable 1 name').getByLabel('Amount').fill('10')

  if ((await page.getByLabel('Hop 1 name').count()) === 0) {
    await page.getByRole('button', { name: 'Add hop' }).click()
  }
  await page.getByLabel('Hop 1 name').fill('Cascade')
  await page.getByRole('listbox').getByRole('button', { name: /^Cascade/ }).first().click()
  await row(page, 'Hop 1 name').getByLabel('Amount').fill('1')
  await row(page, 'Hop 1 name').getByLabel('Boil minutes').fill('60')

  const stats = page.getByRole('region', { name: 'Statistics' })
  await expect(stats).toContainText(/1\.0\d\d/)

  await page.getByRole('button', { name: 'Save recipe' }).click()
  await expect(page).toHaveURL(/\/recipes\/[0-9a-f-]{36}$/)
  await page.reload()
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue(RECIPE_NAME)
  await expect(page.getByLabel('Fermentable 1 name')).toHaveValue(/2-row/i)
  await expect(page.getByLabel('Hop 1 name')).toHaveValue(/Cascade/)
})

test('brew a batch, log readings, see the chart and rate it', async ({ page }) => {
  await signIn(page, '1001', 'Octo Cat')
  await page.goto('/batches/new')
  const recipeOption = page.getByLabel('Recipe').locator('option', { hasText: RECIPE_NAME })
  await page.getByLabel('Recipe').selectOption((await recipeOption.getAttribute('value'))!)
  await page.getByLabel('Batch name').fill(BATCH_NAME)
  await page.getByRole('button', { name: 'Create batch' }).click()
  await expect(page).toHaveURL(/\/batches\/[0-9a-f-]{36}$/)
  batchUrl = new URL(page.url()).pathname
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(BATCH_NAME)
  await expect(page.getByTestId('status-badge')).toHaveText('Planned')

  await page.getByRole('button', { name: 'Mark as fermenting' }).click()
  await expect(page.getByTestId('status-badge')).toHaveText('Fermenting')

  await page.getByLabel('Gravity (SG)').fill('1.055')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Readings' })).toContainText('1.055')
  await page.getByLabel('Gravity (SG)').fill('1.030')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Readings' })).toContainText('1.030')
  await expect(page.getByRole('region', { name: 'Fermentation' })).toContainText('1.030')
  await expect(page.getByRole('img', { name: /Fermentation chart/ })).toBeVisible()

  await page.getByRole('link', { name: 'Rate this batch' }).click()
  await expect(page).toHaveURL(/\/tastings\/new\?batch=/)
  await page.getByLabel('4 out of 5', { exact: true }).check({ force: true })
  await page.getByLabel('Flavor').fill('Clean, citrusy, a little sweet still.')
  await page.getByRole('button', { name: 'Save tasting' }).click()
  await expect(page).toHaveURL(/\/tastings$/)
  await expect(page.getByRole('main')).toContainText(BATCH_NAME)
  await expect(page.getByRole('main')).toContainText('4 / 5')
})

test('log and rate a commercial beer', async ({ page }) => {
  await signIn(page, '1001', 'Octo Cat')
  await page.goto('/beers')
  await page.getByLabel('Name', { exact: true }).fill('Pliny the Elder')
  await page.getByLabel('Brewery').fill('Russian River')
  await page.getByLabel('Style').selectOption({ label: '22A Double IPA' })
  await page.getByLabel('ABV (%)').fill('8')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  const item = page.getByRole('listitem').filter({ hasText: 'Pliny the Elder' })
  await expect(item).toContainText('Russian River')
  await item.getByRole('link', { name: 'Rate' }).click()
  await page.getByLabel('5 out of 5', { exact: true }).check({ force: true })
  await page.getByRole('button', { name: 'Save tasting' }).click()
  await expect(page.getByRole('main')).toContainText('Pliny the Elder')
  await expect(page.getByRole('main')).toContainText('5 / 5')
})

test('another user sees none of it', async ({ page }) => {
  await signIn(page, '1002', 'Second Brewer')
  await page.goto('/batches')
  await expect(page.getByRole('main')).toContainText('No batches')
  await page.goto(batchUrl)
  await expect(page.getByRole('alert')).toContainText('No such batch')
  await page.goto('/tastings')
  await expect(page.getByRole('main')).toContainText('Nothing tasted yet')
  await page.goto('/beers')
  await expect(page.getByRole('main')).not.toContainText('Pliny the Elder')
})
