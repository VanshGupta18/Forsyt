import { chromium } from 'playwright'

const shotDir = process.env.SHOT_DIR
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
await page.screenshot({ path: `${shotDir}/waves-zoom.png`, clip: { x: 0, y: 700, width: 1600, height: 300 } })

// check on a dashboard page too
await page.goto('http://localhost:5173/news', { waitUntil: 'networkidle' })
await page.waitForTimeout(1000)
await page.screenshot({ path: `${shotDir}/waves-news.png` })

await browser.close()
