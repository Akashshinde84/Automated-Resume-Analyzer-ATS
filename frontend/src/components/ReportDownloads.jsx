import { useEffect, useRef, useState } from 'react'
import { useWorkspace } from '../context/Workspace'
import { reportPayload, request, saveDownload } from '../lib/api'
import { ErrorNotice, Icon } from './UI'

export function ReportDownloads({ includeMatch = false }) {
  const workspace = useWorkspace()
  const { analysis } = workspace
  const match = includeMatch ? workspace.match : null
  const [busy, setBusy] = useState(null),
    [error, setError] = useState(null),
    [last, setLast] = useState(null),
    [success, setSuccess] = useState(null)
  const active = useRef(null)
  useEffect(() => {
    setError(null)
    setSuccess(null)
    return () => active.current?.abort()
  }, [analysis, match])
  if (!analysis) return null
  async function download(format) {
    setBusy(format)
    setLast(format)
    setError(null)
    setSuccess(null)
    const control = workspace.controller()
    active.current = control
    try {
      const blob = await request('/api/v1/reports', {
        method: 'POST',
        signal: control.signal,
        download: format,
        body: reportPayload(analysis, match, format),
      })
      if (!control.signal.aborted) {
        saveDownload(blob, format)
        setSuccess(`${format.toUpperCase()} download started.`)
      }
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      setBusy(null)
    }
  }
  return (
    <section
      className="card report-downloads"
      aria-labelledby={
        includeMatch ? 'match-report-title' : 'analysis-report-title'
      }
    >
      <div>
        <p className="eyebrow">TAKE YOUR INSIGHTS WITH YOU</p>
        <h2 id={includeMatch ? 'match-report-title' : 'analysis-report-title'}>
          Download {includeMatch ? 'this comparison' : 'this analysis'}
        </h2>
        <p className="muted">
          {includeMatch
            ? 'Current candidate details, skills, score explanations, and evidence-based suggestions.'
            : 'Current candidate details, skills, extraction notes, and source evidence.'}{' '}
          Downloads contain personal information. Keep them private.
        </p>
      </div>
      <div className="report-actions">
        <button
          className="button secondary"
          disabled={Boolean(busy)}
          onClick={() => download('json')}
        >
          <Icon name="document" />
          Download JSON
        </button>
        <button
          className="button primary"
          disabled={Boolean(busy)}
          onClick={() => download('pdf')}
        >
          <Icon name="document" />
          Download PDF
        </button>
      </div>
      {busy && (
        <div className="report-status" role="status">
          <span className="spinner" />
          Preparing {busy.toUpperCase()} report…
          <button
            className="link-button"
            onClick={() => active.current?.abort()}
          >
            Cancel
          </button>
        </div>
      )}
      {success && (
        <p className="fine-print" role="status">
          {success}
        </p>
      )}
      <ErrorNotice error={error} />
      {error && last && (
        <button
          className="button secondary"
          disabled={Boolean(busy)}
          onClick={() => download(last)}
        >
          Retry download
        </button>
      )}
    </section>
  )
}
