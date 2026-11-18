import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { WorkspaceProvider, useWorkspace } from '../context/Workspace'
import { ReportDownloads } from '../components/ReportDownloads'
import * as api from '../lib/api'

const analysis = { id: null, stored: false, report_token: 'signed-analysis' }
const result = {
  id: null,
  analysis_id: null,
  stored: false,
  report_token: 'signed-match',
  result: { scores: { overall: 12.3 } },
  job_description: 'Original job',
}
function Seed() {
  const workspace = useWorkspace()
  return (
    <>
      <button
        onClick={async () => {
          workspace.acceptAnalysis(analysis)
          workspace.setMatch(result, 'Original job')
          workspace.setJob('Edited draft')
        }}
      >
        Seed
      </button>
      <button onClick={workspace.clear}>Clear</button>
    </>
  )
}
function mount() {
  render(
    <MemoryRouter>
      <WorkspaceProvider>
        <Seed />
        <ReportDownloads includeMatch />
      </WorkspaceProvider>
    </MemoryRouter>,
  )
}
it('scopes report sources and binds snapshots to the original comparison job', () => {
  expect(api.reportPayload(analysis, result, 'json')).toMatchObject({
    snapshot: analysis,
    job_description: 'Original job',
    match: { report_token: 'signed-match' },
  })
  expect(() =>
    api.reportPayload(
      { id: 'owned-id' },
      { ...result, analysis_id: 'owned-id', stored: true, id: 'match-id' },
      'pdf',
    ),
  ).toThrow(/Saved analyses/)
  expect(() =>
    api.reportPayload(
      analysis,
      { ...result, analysis_id: 'another-id' },
      'json',
    ),
  ).toThrow(/another analysis/)
})
it('handles report errors with explicit retry and no automatic POST replay', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    status: 409,
    ok: false,
    json: async () => ({ detail: { code: 'storage_disabled' } }),
  })
  const save = vi.spyOn(api, 'saveDownload').mockImplementation(() => {})
  const transport = vi.spyOn(api, 'request')
  mount()
  await userEvent.click(screen.getByText('Seed'))
  await screen.findByRole('button', { name: 'Download JSON' })
  transport.mockRejectedValueOnce(new api.ApiError('Connection interrupted'))
  await userEvent.click(screen.getByRole('button', { name: 'Download JSON' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Connection interrupted',
  )
  expect(save).not.toHaveBeenCalled()
  transport.mockResolvedValueOnce(
    new Blob(['{}'], { type: 'application/json' }),
  )
  await userEvent.click(screen.getByRole('button', { name: 'Retry download' }))
  await waitFor(() => expect(save).toHaveBeenCalledOnce())
  const payload = transport.mock.calls.at(-1)[1].body
  expect(payload.job_description).toBe('Original job')
  expect(payload.snapshot).toEqual(analysis)
})
it('does not start a late report download after results are cleared', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    status: 409,
    ok: false,
    json: async () => ({ detail: { code: 'storage_disabled' } }),
  })
  const save = vi.spyOn(api, 'saveDownload').mockImplementation(() => {})
  const transport = vi.spyOn(api, 'request')
  mount()
  await userEvent.click(screen.getByText('Seed'))
  let finish
  transport.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await userEvent.click(
    await screen.findByRole('button', { name: 'Download PDF' }),
  )
  await userEvent.click(screen.getByText('Clear'))
  await act(async () => finish(new Blob(['%PDF'])))
  expect(save).not.toHaveBeenCalled()
})
it('validates download content types and returns binary bytes', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    status: 200,
    ok: true,
    headers: new Headers({ 'Content-Type': 'text/html' }),
  })
  await expect(
    api.request('/api/v1/reports', { download: 'pdf' }),
  ).rejects.toThrow(/unexpected report format/)
  const blob = new Blob(['%PDF'], { type: 'application/pdf' })
  fetch.mockResolvedValue({
    status: 200,
    ok: true,
    headers: new Headers({ 'Content-Type': 'application/pdf' }),
    blob: async () => blob,
  })
  await expect(
    api.request('/api/v1/reports', { download: 'pdf' }),
  ).resolves.toBe(blob)
})
