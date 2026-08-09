import { chromium } from 'playwright'

const shotDir = process.env.SHOT_DIR
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.waitForTimeout(1800)
await page.screenshot({ path: `${shotDir}/waves-bright-full.png` })
await browser.close()
