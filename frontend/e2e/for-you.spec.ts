import { type Page, expect, test } from '@playwright/test'

/**
 * Plan Phase 4: a new user answers the cold-start questions and gets explained suggestions;
 * once they rate a styled beer their taste shows up. A fresh account each run keeps the
 * cold start deterministic.
 */

async function signIn(page: Page, subject: string, name: string) {
  const become = await page.request.get(`/api/v1/fake-github/become?subject=${subject}&name=${encodeURIComponent(name)}`)
  expect(become.ok()).toBeTruthy()
  await page.goto('/sign-in')
  await page.getByRole('link', { name: 'Continue with GitHub' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toContainText(name)
}

test('cold-start questions, then suggestions from ratings', async ({ page }) => {
  await signIn(page, `${Date.now() % 1_000_000_000}`, 'New Taster')
  await page.goto('/for-you')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('For you')
  await expect(page.getByTestId('cold-start')).toContainText('No tastings tied to a style yet')
  await expect(page.getByTestId('no-suggestions')).toBeVisible()

  await page.getByText('Strong, over 6.5%').click()
  await expect(page).toHaveURL(/strength=strong/)
  await page.getByText('Bitter, hop-forward').click()
  await expect(page).toHaveURL(/bitterness=bitter/)
  await page.getByText('Pale, straw to gold').click()
  await expect(page).toHaveURL(/color=pale/)
  await expect(page.getByRole('radio', { name: 'Pale, straw to gold' })).toBeChecked()
  const suggestions = page.getByTestId('suggestion')
  await expect(suggestions.first()).toContainText('Because of your answers')
  await expect(suggestions.first()).toContainText('IPA')
  await expect(page.getByText('Using your answers:')).toContainText('strong, over 6.5%')

  // Rate a styled beer through the API, the way the tasting form would.
  const origin = new URL(page.url()).origin
  const beer = await page.request.post('/api/v1/beers', {
    data: { name: 'Two Hearted Ale', brewery_name: "Bell's", style: 'american-ipa' },
    headers: { Origin: origin },
  })
  expect(beer.status()).toBe(201)
  const { id } = (await beer.json()) as { id: string }
  const tasting = await page.request.post('/api/v1/tastings', {
    data: { beer_id: id, rating: 4.5 },
    headers: { Origin: origin },
  })
  expect(tasting.status()).toBe(201)

  await page.reload()
  await expect(page.getByTestId('cold-start')).toContainText('1 of the 5 tastings needed')
  await expect(page.getByTestId('rated-styles')).toContainText('21A American IPA')
  await expect(page.getByTestId('rated-styles')).toContainText('4.5 / 5')
  await expect(page.getByTestId('rated-families')).toContainText('21. IPA')
  // Answers are remembered, so the suggestions still show and now blend both reasons.
  await expect(suggestions.first()).toContainText('Because')
})
