import { chromium } from 'playwright'

const shotDir = process.env.SHOT_DIR
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const errors = []
page.on('pageerror', (err) => errors.push(String(err)))
page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()) })

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 20000 })
await page.waitForTimeout(1500)
await page.screenshot({ path: `${shotDir}/fresh-check.png` })
console.log('ERRORS:', JSON.stringify(errors))
console.log('TITLE:', await page.title())
await browser.close()
