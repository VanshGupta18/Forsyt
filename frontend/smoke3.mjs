import { chromium } from 'playwright'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 20000 })
await page.waitForTimeout(1500)

const result = await page.evaluate(() => {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      const webglCanvas = document.querySelector('canvas')
      if (!webglCanvas) return resolve({ error: 'no canvas' })
      const tmp = document.createElement('canvas')
      tmp.width = webglCanvas.width
      tmp.height = webglCanvas.height
      const ctx = tmp.getContext('2d')
      ctx.drawImage(webglCanvas, 0, 0)
      const points = [[50,900],[300,900],[1550,900],[50,50],[1550,50]]
      resolve(points.map(([x,y]) => ({x,y,rgb: Array.from(ctx.getImageData(x,y,1,1).data)})))
    })
  })
})
console.log('PIXELS:', JSON.stringify(result))
await browser.close()
