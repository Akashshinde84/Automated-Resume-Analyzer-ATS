import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { WorkspaceProvider, useWorkspace } from '../context/Workspace'
import { Job } from '../pages/Job'
import { Upload } from '../pages/Upload'
import * as api from '../lib/api'

const resume = {
  id: null,
  stored: false,
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
      <button onClick={() => workspace.acceptAnalysis(resume)}>
        Load fixture
      </button>
      <button onClick={workspace.clear}>Clear fixture</button>
      <span data-testid="analysis-state">
        {workspace.analysis ? 'loaded' : 'empty'}
      </span>
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
it('submits actual resume text and JD anonymously without saving', async () => {
  const transport = vi
    .spyOn(api, 'request')
    .mockResolvedValue({ result: { scores: { overall: 37 } } })
  mount(<Job />)
  await userEvent.click(screen.getByText('Load fixture'))
  await userEvent.type(
    screen.getByRole('textbox', { name: /Role, responsibilities/ }),
    'Required skills: Python.',
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Compare with resume' }),
  )
  await waitFor(() =>
    expect(screen.getByTestId('match-state')).toHaveTextContent('matched'),
  )
  expect(transport.mock.calls[0][1].body).toEqual({
    resume: { text: resume.parsed.text },
    job_description: 'Required skills: Python.',
    store: false,
  })
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})
it('preserves the job draft on network failure for explicit retry', async () => {
  vi.spyOn(api, 'request').mockRejectedValue(
    new api.ApiError('Matching is temporarily unavailable.'),
  )
  mount(<Job />)
  await userEvent.click(screen.getByText('Load fixture'))
  await userEvent.type(screen.getByRole('textbox'), 'Required: Python')
  await userEvent.click(
    screen.getByRole('button', { name: 'Compare with resume' }),
  )
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'temporarily unavailable',
  )
  expect(screen.getByRole('textbox')).toHaveValue('Required: Python')
})
it('automatically uploads a selected resume and uses the actual result', async () => {
  let finish
  const upload = vi
    .spyOn(api, 'uploadResume')
    .mockImplementation((_file, options) => {
      options.onProgress(100)
      return new Promise((resolve) => {
        finish = resolve
      })
    })
  mount(<Upload />)
  const file = new File(['synthetic'], 'resume.pdf', {
    type: 'application/pdf',
  })
  await userEvent.upload(
    screen.getByLabelText('Choose PDF or DOCX resume'),
    file,
  )
  expect(upload).toHaveBeenCalledOnce()
  expect(upload.mock.calls[0][0]).toBe(file)
  expect(screen.getByRole('status')).toHaveTextContent('Analyzing Skills')
  await act(async () => {
    finish(resume)
    await new Promise((resolve) => setTimeout(resolve, 50))
  })
  await waitFor(() =>
    expect(screen.getByTestId('analysis-state')).toHaveTextContent('loaded'),
  )
})
it('aborts pending upload and ignores its late result when cleared', async () => {
  let finish, signal
  vi.spyOn(api, 'uploadResume').mockImplementation((_file, options) => {
    signal = options.signal
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  mount(<Upload />)
  await userEvent.upload(
    screen.getByLabelText('Choose PDF or DOCX resume'),
    new File(['text'], 'test.pdf'),
  )
  await userEvent.click(screen.getByText('Clear fixture'))
  expect(signal.aborted).toBe(true)
  await act(async () => finish(resume))
  expect(screen.getByTestId('analysis-state')).toHaveTextContent('empty')
})

it('shows precise worker errors and a manual Retry Analysis action', async () => {
  vi.spyOn(api, 'uploadResume').mockRejectedValue(
    new api.ApiError('Document processing timed out.', 504, 'parsing_timeout'),
  )
  mount(<Upload />)
  await userEvent.upload(
    screen.getByLabelText('Choose PDF or DOCX resume'),
    new File(['synthetic'], 'resume.pdf'),
  )
  expect(await screen.findByRole('alert')).toHaveTextContent('timed out')
  expect(
    screen.getByRole('button', { name: 'Retry Analysis' }),
  ).toBeInTheDocument()
})
