import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { WorkspaceProvider, useWorkspace } from '../context/Workspace'
import { Analysis } from '../pages/Analysis'
import { Match } from '../pages/Match'
import { Upload } from '../pages/Upload'

const candidate = {
  name: 'José 林',
  emails: [],
  phones: [],
  linkedin_urls: [],
  github_urls: [],
  portfolio_urls: [],
  education: [],
  work_experience: [],
  projects: [],
  certifications: [],
  provenance: [],
}
const analysis = {
  stored: false,
  parsed: {
    text: '',
    metadata: {
      filename: 'scan.pdf',
      file_type: 'pdf',
      characters: 0,
      page_count: 1,
    },
    skills: [],
    warnings: ['Image-only PDF: OCR is not implemented.'],
  },
  extraction: { candidate, warnings: [], nlp: { status: 'unavailable' } },
}
function Harness({ children }) {
  return (
    <MemoryRouter>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </MemoryRouter>
  )
}
function Seed({ value, result }) {
  const workspace = useWorkspace()
  return (
    <>
      <button
        onClick={() => {
          workspace.acceptAnalysis(value)
          if (result) workspace.setMatch(result)
        }}
      >
        Load fixture
      </button>
      <button onClick={workspace.clear}>Clear</button>
      <span data-testid="session-state">
        {workspace.analysis ? 'loaded' : 'empty'}:
      </span>
    </>
  )
}
describe('resume review', () => {
  it('shows an honest empty state before upload', () => {
    render(
      <Harness>
        <Analysis />
      </Harness>,
    )
    expect(screen.getByText('Your analysis starts here')).toBeInTheDocument()
  })
  it('preserves Unicode, missing fields, scanned warnings, and clears on disconnect', async () => {
    render(
      <Harness>
        <Seed value={analysis} />
        <Analysis />
      </Harness>,
    )
    await userEvent.click(screen.getByText('Load fixture'))
    expect(screen.getByText('José 林')).toBeInTheDocument()
    expect(screen.getByText('No extractable text')).toBeInTheDocument()
    expect(screen.getByText(/Image-only PDF/)).toBeInTheDocument()
    expect(screen.getAllByText('Not identified').length).toBeGreaterThan(0)
    expect(
      screen.getByRole('link', { name: /Try another resume/ }),
    ).toHaveAttribute('href', '/upload')
    await userEvent.click(screen.getByText('Clear'))
    expect(screen.getByTestId('session-state')).toHaveTextContent('empty:')
  })
  it('rejects unsupported drag-and-drop files', () => {
    render(
      <Harness>
        <Upload />
      </Harness>,
    )
    fireEvent.drop(
      screen.getByText('Drop your resume here').closest('.dropzone'),
      { dataTransfer: { files: [new File(['x'], 'resume.exe')] } },
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Only PDF and DOCX')
    expect(screen.queryByText('Connect to analyze')).not.toBeInTheDocument()
  })
})
describe('matching results', () => {
  it('renders only actual scores, handles nulls and displays server suggestions', async () => {
    const result = {
      stored: false,
      result: {
        scores: { overall: 42.7, skill_overlap: 61.0, text_similarity: null },
        score_meaning: 'Project-defined compatibility estimate.',
        warnings: [],
        effective_weights: { skills: 0.7, text: 0.3 },
        weights: {
          required_importance: 2,
          preferred_importance: 1,
          unspecified_importance: 1,
        },
        matched_skills: [],
        missing_required_skills: [],
        preferred_skills: [],
        unspecified_skills: [],
        suggestions: [
          {
            code: 'review_requirement_gap',
            skill: 'Python',
            message:
              'Review the requirement; do not add unsupported qualifications.',
            resume_evidence: [],
          },
        ],
        shared_text_features: [],
      },
    }
    render(
      <Harness>
        <Seed value={analysis} result={result} />
        <Match />
      </Harness>,
    )
    await userEvent.click(screen.getByText('Load fixture'))
    expect(screen.getByRole('img', { name: /42.7%/ })).toBeInTheDocument()
    expect(screen.getByText('61.0%')).toBeInTheDocument()
    expect(screen.getByText('Not available')).toBeInTheDocument()
    expect(screen.getByText(/Review the requirement/)).toBeInTheDocument()
  })
})
it('keeps analysis only in memory and clears it without a login step', async () => {
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  render(
    <Harness>
      <Seed value={analysis} />
    </Harness>,
  )
  await userEvent.click(screen.getByText('Load fixture'))
  expect(screen.getByTestId('session-state')).toHaveTextContent('loaded')
  expect(storage).not.toHaveBeenCalled()
  await userEvent.click(screen.getByText('Clear'))
  expect(screen.getByTestId('session-state')).toHaveTextContent('empty')
})

it('renders grouped education, technologies, links and separate activities', async () => {
  const value = {
    ...analysis,
    extraction: {
      ...analysis.extraction,
      candidate: {
        ...candidate,
        summary: 'Builds document tools.',
        education: [
          {
            institution: 'Example Institute',
            degree: 'B.Tech',
            field: 'AI & ML',
            grade: 'CGPA: 8.4/10',
            raw_text: 'Example Institute',
            provenance: [],
            warnings: [],
          },
        ],
        projects: [
          {
            name: 'Document Tool',
            technologies: ['Python', 'React'],
            urls: ['https://github.com/example/tool'],
            description: 'Built a parser using Python.',
            raw_text: 'Document Tool',
            provenance: [],
            warnings: [],
          },
        ],
        activities: [
          {
            name: 'Sports',
            description: 'Organized a football event.',
            raw_text: 'Football',
            provenance: [],
            warnings: [],
          },
        ],
      },
    },
  }
  render(
    <Harness>
      <Seed value={value} />
      <Analysis />
    </Harness>,
  )
  await userEvent.click(screen.getByText('Load fixture'))
  expect(screen.getByText('Technologies: Python, React')).toBeInTheDocument()
  expect(screen.getByText('Grade: CGPA: 8.4/10')).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Extracurricular activities' }),
  ).toBeInTheDocument()
  expect(screen.getByText('Organized a football event.')).toBeInTheDocument()
})
