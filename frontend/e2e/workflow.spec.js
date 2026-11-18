import { test, expect } from '@playwright/test'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import AxeBuilder from '@axe-core/playwright'

async function accessibility(page, label, testInfo) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  await writeFile(
    testInfo.outputPath(`${label}-accessibility.json`),
    JSON.stringify(
      {
        path: new URL(page.url()).pathname,
        violations: results.violations,
        incomplete: results.incomplete.map((item) => ({
          id: item.id,
          impact: item.impact,
        })),
      },
      null,
      2,
    ),
  )
  expect(
    results.violations.map((item) => ({
      id: item.id,
      impact: item.impact,
      nodes: item.nodes.map((node) => ({
        target: node.target,
        failureSummary: node.failureSummary,
      })),
    })),
  ).toEqual([])
}

const fixture = (name) => path.join(process.env.E2E_FILES_DIR, name)
async function openUpload(page) {
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'AI Resume Analyzer', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(
    page.getByLabel('Private access token', { exact: true }),
  ).toHaveCount(0)
}
async function analyze(page, filename = 'synthetic.docx') {
  await page.getByRole('link', { name: 'Upload resume', exact: true }).click()
  const response = page.waitForResponse(
    (response) =>
      response.url().includes('/resumes/analyze?') &&
      response.request().method() === 'POST',
  )
  await page
    .getByLabel('Choose PDF or DOCX resume')
    .setInputFiles(fixture(filename))
  const data = await (await response).json()
  await expect(
    page.getByRole('heading', { name: 'Your experience, organized' }),
  ).toBeVisible()
  return data
}
async function download(page, label, destination) {
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: label, exact: true }).click()
  const item = await pending
  await item.saveAs(destination)
  return readFile(destination)
}

test('real stateless upload, extraction, match, safe retry and scoped JSON/PDF downloads', async ({
  page,
}, testInfo) => {
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await openUpload(page)
  const analysis = await analyze(page)
  expect(analysis.id).toBeNull()
  expect(analysis.parsed.text).toContain('Python')
  expect(analysis.readiness.status).toBe('computed')
  expect(
    analysis.readiness.categories.reduce((sum, item) => sum + item.score, 0),
  ).toBeCloseTo(analysis.readiness.score, 2)
  await expect(
    page.getByRole('img', {
      name: `ATS readiness estimate: ${analysis.readiness.score} out of 100`,
    }),
  ).toBeVisible()
  await expect(page.getByRole('progressbar')).toHaveCount(7)
  await expect(
    page.getByRole('link', { name: /GitHub repository/ }),
  ).toHaveAttribute('href', 'https://github.com/example/resume-platform')
  await page.getByLabel('Filter by priority').selectOption('low')
  await expect(page.locator('.priority-high')).toHaveCount(0)
  await page.getByLabel('Filter by priority').selectOption('all')
  expect(analysis.extraction.candidate.name).toBe('Sofía Rivera')
  await accessibility(page, 'analysis', testInfo)
  expect(analysis.parsed.skills.map((skill) => skill.name)).toEqual(
    expect.arrayContaining(['Python', 'SQL', 'React']),
  )
  await expect(
    page.getByRole('heading', { name: 'Sofía Rivera', exact: true }),
  ).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: testInfo.outputPath('desktop-analysis.png'),
    fullPage: true,
  })
  const initial = JSON.parse(
    (
      await download(
        page,
        'Download JSON',
        testInfo.outputPath('analysis.json'),
      )
    ).toString('utf8'),
  )
  expect(initial.match).toBeNull()
  expect(initial.analysis.readiness).toEqual(analysis.readiness)
  await page.getByRole('link', { name: 'Compare with a job' }).click()
  const job = 'Required skills:\nPython\nSQL\nPreferred skills:\nDocker'
  await page
    .getByRole('textbox', {
      name: 'Role, responsibilities, and qualifications',
    })
    .fill(job)
  await page.route('**/api/v1/jobs/match', (route) => route.abort('failed'), {
    times: 1,
  })
  await page.getByRole('button', { name: 'Compare with resume' }).click()
  await expect(page.getByRole('alert')).toContainText('Cannot reach the API')
  await expect(page.getByRole('textbox')).toHaveValue(job)
  const pending = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/jobs/match'),
  )
  await page.getByRole('button', { name: 'Compare with resume' }).click()
  const matched = await (await pending).json()
  await expect(
    page.getByRole('heading', { name: 'See how your experience aligns' }),
  ).toBeVisible()
  await expect(
    page.getByRole('img', {
      name: `Overall compatibility estimate: ${matched.result.scores.overall.toFixed(1)}%`,
    }),
  ).toBeVisible()
  await expect(page.getByText('80.0%', { exact: true })).toBeVisible()
  await accessibility(page, 'match', testInfo)
  // An edited draft must not change the job associated with an existing result/report.
  await page.getByRole('link', { name: 'Edit job description' }).click()
  await page.getByRole('textbox').fill('A new draft that has not been compared')
  await page.getByRole('link', { name: 'Match results', exact: true }).click()
  await page.route('**/api/v1/reports', (route) => route.abort('failed'), {
    times: 1,
  })
  await page.getByRole('button', { name: 'Download JSON', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Cannot reach the API')
  const report = JSON.parse(
    (
      await download(
        page,
        'Retry download',
        testInfo.outputPath('comparison.json'),
      )
    ).toString('utf8'),
  )
  expect(report.analysis.extraction.candidate).toEqual(
    analysis.extraction.candidate,
  )
  expect(report.match.result).toEqual(matched.result)
  expect(report.match.job_description).toBe(job)
  expect(JSON.stringify(report)).not.toContain('report_token')
  const pdf = await download(
    page,
    'Download PDF',
    testInfo.outputPath('comparison.pdf'),
  )
  expect(pdf.subarray(0, 5).toString()).toBe('%PDF-')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: testInfo.outputPath('desktop-match.png'),
    fullPage: true,
  })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  await page.getByRole('button', { name: 'Clear current analysis' }).click()
  await expect(
    page.getByRole('heading', { name: 'A clearer comparison awaits' }),
  ).toBeVisible()
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0)
  expect(pageErrors).toEqual([])
})

test('anonymous PDF analysis is isolated from fresh browser state and private history', async ({
  page,
}) => {
  await openUpload(page)
  let sentAuthorization = false
  page.on('request', (r) => {
    if (r.url().includes('/api/v1/'))
      sentAuthorization ||= Boolean(r.headers()['authorization'])
  })
  const data = await analyze(page, 'synthetic.pdf')
  expect(data.id).toBeNull()
  expect(data.stored).toBe(false)
  expect(await page.getByRole('link', { name: 'Saved history' }).count()).toBe(
    0,
  )
  const response = await page.request.get(
    `${process.env.VITE_API_BASE_URL}/api/v1/analyses`,
  )
  expect(response.status()).toBe(403)
  const fresh = await page.context().browser().newPage()
  try {
    await fresh.goto(`${process.env.E2E_BASE_URL}/analysis`)
    await expect(
      fresh.getByRole('heading', { name: 'Your analysis starts here' }),
    ).toBeVisible()
  } finally {
    await fresh.close()
  }
  expect(sentAuthorization).toBe(false)
})

test('mobile navigation, empty/scanned states and responsive upload', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await accessibility(page, 'mobile-home', testInfo)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  await expect(
    page.getByRole('button', { name: 'Toggle navigation' }),
  ).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('mobile-home.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Toggle navigation' }).click()
  await page.getByRole('link', { name: 'Upload resume', exact: true }).click()
  await accessibility(page, 'mobile-upload', testInfo)
  await page.screenshot({
    path: testInfo.outputPath('mobile-upload.png'),
    fullPage: true,
  })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  await page
    .getByLabel('Choose PDF or DOCX resume')
    .setInputFiles(fixture('scan.pdf'))
  await expect(
    page.getByText('No extractable text', { exact: true }),
  ).toBeVisible()
  await accessibility(page, 'mobile-scanned', testInfo)
  await expect(
    page.getByRole('link', { name: 'Try another resume' }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  await page.screenshot({
    path: testInfo.outputPath('mobile-scanned.png'),
    fullPage: true,
  })
})

test('privacy, direct upload keyboard access and invalid file handling', async ({
  page,
}, testInfo) => {
  await page.goto('/privacy')
  await accessibility(page, 'privacy', testInfo)
  await openUpload(page)
  await accessibility(page, 'anonymous-upload', testInfo)
  const browse = page.getByRole('button', { name: 'Browse files', exact: true })
  await browse.focus()
  await expect(browse).toBeFocused()
  await page.getByLabel('Choose PDF or DOCX resume').setInputFiles({
    name: 'bad.exe',
    mimeType: 'application/octet-stream',
    buffer: Buffer.from('invalid'),
  })
  await expect(page.getByRole('alert')).toContainText('Only PDF and DOCX')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
