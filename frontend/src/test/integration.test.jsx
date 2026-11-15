import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { WorkspaceProvider, useWorkspace } from '../context/Workspace'
import { History } from '../pages/History'
import { Job } from '../pages/Job'
import { SavedMatches } from '../components/SavedMatches'
import { Upload } from '../pages/Upload'
import * as api from '../lib/api'

const resume = {
  id: 'aaaaaaaa-1111-1111-1111-111111111111',
  stored: true,
  parsed: {
    text: 'Skills: Python, SQL',
    metadata: { filename: 'synthetic.docx' },
  },
  extraction: { candidate: { name: null } },
}
function Seed() {
  const workspace = useWorkspace()
  return (
    <>
      <button
        onClick={async () => {
          await workspace.connect(
            'synthetic-test-token',
            new AbortController().signal,
          )
          workspace.acceptAnalysis(resume)
        }}
      >
        Connect fixture
      </button>
      <span data-testid="analysis-state">
        {workspace.analysis?.id || 'empty'}
      </span>
      <button onClick={workspace.disconnect}>Disconnect fixture</button>
      <span data-testid="match-state">
        {workspace.match ? 'matched' : 'none'}
      </span>
    </>
  )
}
function mount(children) {
  render(
    <MemoryRouter>
      <WorkspaceProvider>
        <Seed />
        {children}
      </WorkspaceProvider>
    </MemoryRouter>,
  )
}
const ok = (value) => ({ status: 200, ok: true, json: async () => value })

it('submits the actual JD with the stored analysis ID and explicit save consent', async () => {
  const fetch = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(ok({ items: [] }))
    .mockResolvedValueOnce(ok({ result: { scores: { overall: 37 } } }))
  mount(<Job />)
  await userEvent.click(screen.getByText('Connect fixture'))
  const input = await screen.findByRole('textbox', {
    name: /Role, responsibilities/,
  })
  await userEvent.type(input, 'Required skills: Python. Preferred skills: SQL.')
  await userEvent.click(
    screen.getByRole('checkbox', { name: /Save this comparison/ }),
  )
  await userEvent.click(
    screen.getByRole('button', { name: /Compare with resume/ }),
  )
  await waitFor(() =>
    expect(screen.getByTestId('match-state')).toHaveTextContent('matched'),
  )
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    analysis_id: resume.id,
    job_description: 'Required skills: Python. Preferred skills: SQL.',
    store: true,
  })
})

it('renders server failure messages and preserves the pasted job for retry', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(ok({ items: [] }))
    .mockResolvedValueOnce({
      status: 503,
      ok: false,
      json: async () => ({
        detail: {
          code: 'matching_unavailable',
          message: 'Matching is temporarily unavailable.',
        },
      }),
    })
  mount(<Job />)
  await userEvent.click(screen.getByText('Connect fixture'))
  await userEvent.type(await screen.findByRole('textbox'), 'Required: Python')
  await userEvent.click(
    screen.getByRole('button', { name: /Compare with resume/ }),
  )
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Matching is temporarily unavailable.',
  )
  expect(screen.getByRole('textbox')).toHaveValue('Required: Python')
})

it('lists authenticated history and only deletes after confirmation, clearing the current analysis', async () => {
  let deleted = false
  const fetch = vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(async (url, options) => {
      if (options.method === 'DELETE') {
        deleted = true
        return { status: 204 }
      }
      return ok({
        items: deleted
          ? []
          : [
              {
                id: resume.id,
                file_type: 'docx',
                created_at: '2026-01-01T12:00:00Z',
                expires_at: '2026-01-08T12:00:00Z',
              },
            ],
        total: deleted ? 0 : 1,
      })
    })
  mount(<History />)
  await userEvent.click(screen.getByText('Connect fixture'))
  await userEvent.click(
    await screen.findByRole('button', { name: 'Delete', exact: true }),
  )
  expect(
    fetch.mock.calls.some(([, options]) => options.method === 'DELETE'),
  ).toBe(false)
  const dialog = screen.getByRole('dialog')
  await userEvent.click(
    within(dialog).getByRole('button', { name: 'Keep analysis' }),
  )
  expect(deleted).toBe(false)
  await userEvent.click(
    screen.getByRole('button', { name: 'Delete', exact: true }),
  )
  await userEvent.click(
    within(screen.getByRole('dialog')).getByRole('button', {
      name: 'Delete permanently',
    }),
  )
  await screen.findByText('Nothing saved yet')
  expect(deleted).toBe(true)
  expect(screen.getByTestId('analysis-state')).toHaveTextContent('empty')
})

it('loads saved comparisons into actual match state', async () => {
  const saved = {
    ...resume,
    match_count: 1,
    matches: [
      {
        id: 'match-id',
        created_at: '2026-01-01',
        job_description: 'Required: Python',
        result: { scores: { overall: 23.4 } },
      },
    ],
  }
  mount(<SavedMatches analysis={saved} />)
  await userEvent.click(screen.getByRole('button', { name: 'View comparison' }))
  expect(screen.getByTestId('match-state')).toHaveTextContent('matched')
})

it('uploads the selected file without saving by default and uses the real response', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(ok({ items: [] }))
  let finish
  const upload = vi
    .spyOn(api, 'uploadResume')
    .mockImplementation((_file, _token, options) => {
      options.onProgress(100)
      return new Promise((resolve) => {
        finish = resolve
      })
    })
  mount(<Upload />)
  await userEvent.click(screen.getByText('Connect fixture'))
  await waitFor(() =>
    expect(screen.getByTestId('analysis-state')).toHaveTextContent(resume.id),
  )
  const file = new File(['synthetic PDF content'], 'synthetic.pdf', {
    type: 'application/pdf',
  })
  await userEvent.upload(
    screen.getByLabelText('Choose PDF or DOCX resume'),
    file,
  )
  await userEvent.click(screen.getByRole('button', { name: 'Analyze resume' }))
  expect(screen.getByRole('status')).toHaveTextContent('Analyzing your resume')
  expect(upload.mock.calls[0][0]).toBe(file)
  expect(upload.mock.calls[0][2].store).toBe(false)
  await act(async () =>
    finish({ ...resume, id: 'new-server-analysis', stored: false }),
  )
  expect(screen.getByTestId('analysis-state')).toHaveTextContent(
    'new-server-analysis',
  )
})

it('ignores a late upload response after disconnect clears the session', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(ok({ items: [] }))
  let finish, signal
  vi.spyOn(api, 'uploadResume').mockImplementation((_file, _token, options) => {
    signal = options.signal
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  mount(<Upload />)
  await userEvent.click(screen.getByText('Connect fixture'))
  await waitFor(() =>
    expect(screen.getByTestId('analysis-state')).toHaveTextContent(resume.id),
  )
  await userEvent.upload(
    screen.getByLabelText('Choose PDF or DOCX resume'),
    new File(['text'], 'test.pdf'),
  )
  await userEvent.click(screen.getByRole('button', { name: 'Analyze resume' }))
  await userEvent.click(screen.getByText('Disconnect fixture'))
  expect(signal.aborted).toBe(true)
  await act(async () => finish(resume))
  expect(screen.getByTestId('analysis-state')).toHaveTextContent('empty')
})
