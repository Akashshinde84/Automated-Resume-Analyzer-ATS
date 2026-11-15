import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { request } from '../lib/api'
import { EmptyState, ErrorNotice, Icon, PageHeading } from '../components/UI'
export function Job() {
  const workspace = useWorkspace(),
    navigate = useNavigate(),
    active = useRef(null)
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(null),
    [store, setStore] = useState(false)
  useEffect(() => () => active.current?.abort(), [])
  if (!workspace.analysis?.parsed.text.trim())
    return (
      <>
        <PageHeading title="Add the opportunity" />
        <EmptyState
          title="A readable resume comes first"
          to="/upload"
          label="Upload a resume"
        >
          Analyze a text-based resume before comparing it with a job
          description.
        </EmptyState>
      </>
    )
  async function submit(event) {
    event.preventDefault()
    if (!workspace.token) {
      workspace.setSessionOpen(true)
      return
    }
    setBusy(true)
    setError(null)
    const control = workspace.controller()
    active.current = control
    try {
      const analysis = workspace.analysis
      const result = await request('/api/v1/jobs/match', workspace.token, {
        method: 'POST',
        signal: control.signal,
        body: {
          ...(analysis.id
            ? { analysis_id: analysis.id }
            : { resume: { text: analysis.parsed.text } }),
          job_description: workspace.job,
          store: store && analysis.stored && workspace.historyAvailable,
        },
      })
      if (!control.signal.aborted) {
        workspace.setMatch(result, workspace.job)
        navigate('/match')
      }
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="STEP 03 / THE OPPORTUNITY"
        title="What’s your next role?"
        description="Paste the full job description. Clear required and preferred sections help identify the role’s priorities."
      />
      <div className="job-layout">
        <form className="card job-form" onSubmit={submit}>
          <div className="card-heading">
            <h2>Job description</h2>
            <span className="badge">Plain text</span>
          </div>
          <ErrorNotice error={error} />
          {error?.status === 0 && store && (
            <p className="notice warning">
              The request may have completed on the server. Check saved
              comparisons before retrying to avoid a duplicate.
            </p>
          )}
          <label htmlFor="job-description">
            Role, responsibilities, and qualifications
          </label>
          <textarea
            id="job-description"
            rows={17}
            maxLength={50000}
            required
            value={workspace.job}
            disabled={busy}
            onChange={(event) => workspace.setJob(event.target.value)}
            placeholder="Paste the job description here…"
            aria-describedby="job-help"
          />
          <div className="textarea-footer">
            <small id="job-help">
              Include the required skills and preferred qualifications.
            </small>
            <span>{workspace.job.length.toLocaleString()} / 50,000</span>
          </div>
          {workspace.analysis.stored && workspace.historyAvailable && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={store}
                disabled={busy}
                onChange={(event) => setStore(event.target.checked)}
              />
              <span>
                Save this comparison with my analysis
                <small>
                  The pasted job description and match result will be stored.
                </small>
              </span>
            </label>
          )}
          <div className="form-footer">
            <Link to="/analysis" className="button text-button">
              Back to analysis
            </Link>
            <button
              className="button primary"
              disabled={busy || !workspace.job.trim()}
            >
              {busy ? (
                <>
                  <span className="spinner" />
                  Comparing evidence…
                </>
              ) : (
                <>
                  Compare with resume
                  <Icon name="arrow" />
                </>
              )}
            </button>
          </div>
          {busy && (
            <p role="status" className="fine-print">
              Comparing normalized skills and professional text.{' '}
              <button
                className="link-button"
                type="button"
                onClick={() => active.current?.abort()}
              >
                Cancel
              </button>
            </p>
          )}
        </form>
        <aside>
          <div className="card guidance-card">
            <p className="eyebrow">COMPARING WITH</p>
            <Icon name="document" size={28} />
            <h2>
              {workspace.analysis.extraction.candidate.name ||
                'Your current resume'}
            </h2>
            <p className="muted break-word">
              {workspace.analysis.parsed.metadata.filename}
            </p>
            <Link to="/analysis">Review extracted details →</Link>
            <hr />
            <h3>A score you can understand</h3>
            <p className="muted">
              The backend combines skill coverage and TF-IDF text similarity.
              You’ll see each component, its weight, and the supporting
              evidence.
            </p>
            <p className="fine-print">
              This is a project-defined estimate, not an ATS score or a hiring
              probability. Personal characteristics do not contribute to
              scoring.
            </p>
          </div>
        </aside>
      </div>
    </>
  )
}
