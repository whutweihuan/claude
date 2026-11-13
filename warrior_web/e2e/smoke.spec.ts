import { expect, test } from '@playwright/test'

test('首屏标题与基线截图', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle('warrior_web')
  await expect(page).toHaveScreenshot('smoke.png')
})
