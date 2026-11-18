import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { Readiness } from '../components/Readiness'

const result = {
  score: 62.5,
  version: '1.0.0',
  label:
    'Project-defined ATS readiness estimate; not an official employer ATS score.',
  formula: 'score = sum(category score)',
  categories: [
    {
      key: 'skills',
      label: 'Skills presentation',
      score: 10,
      maximum: 15,
      checks: [
        {
          code: 'applied',
          label: 'Applied skills',
          earned: 0,
          maximum: 5,
          reason: 'No project evidence detected.',
          evidence: ['Skills: Python'],
        },
      ],
    },
  ],
  strengths: ['A recognizable Skills section'],
  recommendations: [
    {
      code: 'contact',
      priority: 'high',
      section: 'contact',
      problem: 'No readable contact found.',
      why: 'Readers need a way to contact you.',
      suggestion: 'Add an email address.',
      possible_points: 8,
      evidence: [],
    },
    {
      code: 'metrics',
      priority: 'low',
      section: 'projects',
      problem: 'No measurable detail found.',
      why: 'Evidence clarifies scale.',
      suggestion: 'Use real measurements only.',
      possible_points: 4,
      evidence: [],
    },
  ],
  limitations: ['Independent of job matching.'],
}

it('displays the returned score and evidence and filters recommendations by priority', async () => {
  render(<Readiness result={result} />)
  expect(
    screen.getByRole('img', {
      name: 'ATS readiness estimate: 62.5 out of 100',
    }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('progressbar', { name: 'Skills presentation' }),
  ).toHaveAttribute('value', '10')
  await userEvent.click(screen.getByText('Skills presentation'))
  expect(screen.getByText('Skills: Python')).toBeVisible()
  await userEvent.selectOptions(
    screen.getByLabelText('Filter by priority'),
    'high',
  )
  expect(screen.getByText('No readable contact found.')).toBeVisible()
  expect(
    screen.queryByText('No measurable detail found.'),
  ).not.toBeInTheDocument()
  expect(screen.getByText(/not guaranteed/)).toBeVisible()
})

it('shows unavailable readiness for a scan without fabricating a zero score', () => {
  render(
    <Readiness
      result={{ ...result, score: null, strengths: [], recommendations: [] }}
    />,
  )
  expect(
    screen.getByRole('img', { name: 'ATS readiness estimate: unavailable' }),
  ).toBeInTheDocument()
  expect(screen.getByText('Unavailable')).toBeVisible()
})
