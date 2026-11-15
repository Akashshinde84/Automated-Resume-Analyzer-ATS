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
async function connect(page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Connect backend' }).click()
  await page.getByRole('button', { name: 'Check API health' }).click()
  await expect(page.getByRole('status')).toContainText('API is reachable')
  await page
    .getByLabel('Private access token', { exact: true })
    .fill(process.env.E2E_OWNER_TOKEN)
  await page.getByRole('button', { name: 'Connect securely' }).click()
  await expect(
    page.getByRole('button', { name: 'Disconnect & clear session' }),
  ).toBeVisible()
}
async function analyze(page, save = false, filename = 'synthetic.docx') {
  await page.getByRole('link', { name: 'Upload resume', exact: true }).click()
  await page
    .getByLabel('Choose PDF or DOCX resume')
    .setInputFiles(fixture(filename))
  if (save)
    await page.getByRole('checkbox', { name: /Save this analysis/ }).check()
  const response = page.waitForResponse(
    (response) =>
      response.url().includes('/resumes/analyze?') &&
      response.request().method() === 'POST',
  )
  await page
    .getByRole('button', { name: 'Analyze resume', exact: true })
    .click()
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
  await connect(page)
  const analysis = await analyze(page)
  expect(analysis.id).toBeNull()
  expect(analysis.parsed.text).toContain('Python')
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
  await page.getByRole('button', { name: 'Disconnect & clear session' }).click()
  await expect(
    page.getByRole('heading', { name: 'A clearer comparison awaits' }),
  ).toBeVisible()
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0)
  expect(pageErrors).toEqual([])
})

test('saved PDF analysis, stored match, private history reopening, reports and confirmed deletion', async ({
  page,
}, testInfo) => {
  await connect(page)
  const analysis = await analyze(page, true, 'synthetic.pdf')
  expect(analysis.id).toBeTruthy()
  await page.getByRole('link', { name: 'Compare with a job' }).click()
  await page
    .getByRole('textbox')
    .fill('Required: Python, SQL. Preferred: Docker.')
  await page.getByRole('checkbox', { name: /Save this comparison/ }).check()
  await page.getByRole('button', { name: 'Compare with resume' }).click()
  await expect(
    page.getByText('Comparison saved', { exact: true }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Saved history' }).click()
  await page.getByRole('button', { name: 'Open analysis' }).first().click()
  await page.getByRole('button', { name: 'View comparison' }).first().click()
  const report = JSON.parse(
    (
      await download(page, 'Download JSON', testInfo.outputPath('saved.json'))
    ).toString('utf8'),
  )
  expect(report.analysis.id).toBe(analysis.id)
  expect(report.match.id).toBeTruthy()
  await page.getByRole('link', { name: 'Saved history' }).click()
  await page
    .getByRole('button', { name: 'Delete', exact: true })
    .first()
    .click()
  await page.getByRole('button', { name: 'Keep analysis' }).click()
  await expect(
    page.getByRole('button', { name: 'Open analysis' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await page.getByRole('button', { name: 'Delete permanently' }).click()
  await expect(
    page.getByRole('heading', { name: 'Nothing saved yet' }),
  ).toBeVisible()
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
  await page.getByRole('button', { name: 'Connect backend' }).click()
  await page
    .getByLabel('Private access token', { exact: true })
    .fill(process.env.E2E_OWNER_TOKEN)
  await page.getByRole('button', { name: 'Connect securely' }).click()
  await expect(
    page.getByRole('button', { name: 'Disconnect & clear session' }),
  ).toBeVisible()
  await page
    .getByLabel('Choose PDF or DOCX resume')
    .setInputFiles(fixture('scan.pdf'))
  await page
    .getByRole('button', { name: 'Analyze resume', exact: true })
    .click()
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

test('privacy and connection dialog accessibility with keyboard containment', async ({
  page,
}, testInfo) => {
  await page.goto('/privacy')
  await accessibility(page, 'privacy', testInfo)
  const button = page.getByRole('button', { name: 'Connect backend' })
  await button.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await accessibility(page, 'connection-dialog', testInfo)
  for (let index = 0; index < 9; index++) {
    await page.keyboard.press('Tab')
    expect(
      await page.evaluate(() =>
        Boolean(document.activeElement.closest('dialog[open]')),
      ),
    ).toBe(true)
  }
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(button).toBeFocused()
})
