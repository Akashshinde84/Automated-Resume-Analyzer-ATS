import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { request, scoreLabel } from '../lib/api'
import { ErrorNotice } from './UI'

export function SavedMatches({ analysis }) {
  const workspace = useWorkspace(),
    navigate = useNavigate()
  const [items, setItems] = useState(analysis.matches || [])
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(null)
  const active = useRef(null)
  useEffect(() => () => active.current?.abort(), [])
  async function more() {
    const control = workspace.controller()
    active.current = control
    setBusy(true)
    setError(null)
    try {
      const result = await request(
        `/api/v1/analyses/${analysis.id}?match_limit=20&match_offset=${items.length}`,
        workspace.token,
        { signal: control.signal },
      )
      if (!control.signal.aborted)
        setItems((current) => [...current, ...result.matches])
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      setBusy(false)
    }
  }
  if (!analysis.match_count) return null
  return (
    <section className="card history-card">
      <div className="card-heading">
        <h2>Saved comparisons</h2>
        <span className="count">{analysis.match_count}</span>
      </div>
      <ErrorNotice error={error} />
      {items.map((item) => (
        <article key={item.id} className="history-row">
          <div>
            <h3>
              Compatibility estimate: {scoreLabel(item.result.scores.overall)}
            </h3>
            <p>{new Date(item.created_at).toLocaleString()}</p>
            <details className="evidence">
              <summary>Saved job description</summary>
              <p className="preserve-lines">{item.job_description}</p>
            </details>
          </div>
          <button
            className="button secondary"
            onClick={() => {
              workspace.setJob(item.job_description)
              workspace.setMatch(
                {
                  id: item.id,
                  analysis_id: analysis.id,
                  stored: true,
                  result: item.result,
                },
                item.job_description,
              )
              navigate('/match')
            }}
          >
            View comparison
          </button>
        </article>
      ))}
      {items.length < analysis.match_count && (
        <button className="button secondary" disabled={busy} onClick={more}>
          {busy ? 'Loading…' : 'Load more comparisons'}
        </button>
      )}
    </section>
  )
}
