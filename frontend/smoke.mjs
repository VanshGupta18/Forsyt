const FRONTEND = process.env.SMOKE_FRONTEND ?? 'http://127.0.0.1:5173'
const API = process.env.SMOKE_API ?? 'http://127.0.0.1:5001'

const checks = [
  { name: 'frontend', url: `${FRONTEND}/` },
  { name: 'api-health', url: `${API}/health` },
  { name: 'api-home-bundle', url: `${API}/api/pages/home` },
]

let failed = 0

for (const check of checks) {
  try {
    const res = await fetch(check.url)
    if (!res.ok) {
      console.error(`FAIL ${check.name}: ${check.url} -> ${res.status}`)
      failed += 1
      continue
    }
    console.log(`OK ${check.name}: ${res.status}`)
  } catch (err) {
    console.error(`FAIL ${check.name}:`, err)
    failed += 1
  }
}

if (failed) {
  process.exit(1)
}

console.log('Smoke checks passed')
