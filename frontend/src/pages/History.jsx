import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { request } from '../lib/api'
import {
  EmptyState,
  ErrorNotice,
  PageHeading,
  Skeleton,
  trapDialogTab,
} from '../components/UI'

export function History() {
  const workspace = useWorkspace(),
    navigate = useNavigate()
  const [page, setPage] = useState(null),
    [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(null),
    [selected, setSelected] = useState(null),
    [busy, setBusy] = useState(false)
  const dialog = useRef(null),
    active = useRef(null)
  useEffect(() => {
    if (!workspace.token || !workspace.historyAvailable) return
    const control = new AbortController()
    setLoading(true)
    setError(null)
    request(`/api/v1/analyses?limit=20&offset=${offset}`, workspace.token, {
      signal: control.signal,
    })
      .then(setPage)
      .catch((failure) => {
        if (failure.name !== 'AbortError') setError(failure)
      })
      .finally(() => {
        if (!control.signal.aborted) setLoading(false)
      })
    return () => control.abort()
  }, [workspace.token, workspace.historyAvailable, offset, revision])
  useEffect(() => {
    if (selected) dialog.current.showModal()
    else dialog.current?.close()
  }, [selected])
  useEffect(() => () => active.current?.abort(), [])
  async function load(id) {
    setBusy(true)
    setError(null)
    const control = workspace.controller()
    active.current = control
    try {
      const result = await request(`/api/v1/analyses/${id}`, workspace.token, {
        signal: control.signal,
      })
      if (!control.signal.aborted) {
        workspace.acceptAnalysis(result)
        navigate('/analysis')
      }
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      setBusy(false)
    }
  }
  async function remove() {
    setBusy(true)
    setError(null)
    const control = workspace.controller()
    active.current = control
    try {
      await request(`/api/v1/analyses/${selected.id}`, workspace.token, {
        method: 'DELETE',
        signal: control.signal,
      })
      if (!control.signal.aborted) {
        if (workspace.analysis?.id === selected.id) workspace.clear()
        setSelected(null)
        if (page.items.length === 1 && offset)
          setOffset(Math.max(0, offset - 20))
        else setRevision((value) => value + 1)
      }
    } catch (failure) {
      if (failure.name !== 'AbortError') {
        setSelected(null)
        setError(failure)
      }
    } finally {
      workspace.release(control)
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeading
        title="Private analysis history"
        description="Only explicitly saved analyses appear here. Deletion also removes associated job descriptions and matches."
      />
      {!workspace.token || !workspace.historyAvailable ? (
        <EmptyState
          title="Saved history is not enabled"
          to="/privacy"
          label="Understand storage"
          icon="shield"
        >
          Connect to a backend with secure persistence enabled. Stateless
          analysis is available without saved history.
        </EmptyState>
      ) : (
        <>
          <ErrorNotice error={error} />
          {error && (
            <button
              className="button secondary"
              onClick={() => setRevision((value) => value + 1)}
            >
              Retry history
            </button>
          )}
          {loading ? (
            <Skeleton label="Loading private history…" />
          ) : (
            page &&
            (page.items.length ? (
              <section className="card history-card">
                <div className="card-heading">
                  <h2>Saved analyses</h2>
                  <span className="badge">{page.total} total</span>
                </div>
                {page.items.map((item) => (
                  <article className="history-row" key={item.id}>
                    <div>
                      <h3>Analysis {item.id.slice(0, 8)}</h3>
                      <p>
                        {item.file_type.toUpperCase()} ·{' '}
                        {new Date(item.created_at).toLocaleString()}
                      </p>
                      <small>
                        Expires {new Date(item.expires_at).toLocaleString()}
                      </small>
                    </div>
                    <div className="history-actions">
                      <button
                        className="button secondary"
                        disabled={busy}
                        onClick={() => load(item.id)}
                      >
                        Open analysis
                      </button>
                      <button
                        className="button danger-text"
                        disabled={busy}
                        onClick={() => setSelected(item)}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                ))}
                <div className="pagination">
                  <button
                    className="button secondary"
                    disabled={!offset || busy}
                    onClick={() => setOffset(Math.max(0, offset - 20))}
                  >
                    Previous
                  </button>
                  <span>
                    {offset + 1}–{offset + page.items.length} of {page.total}
                  </span>
                  <button
                    className="button secondary"
                    disabled={offset + page.items.length >= page.total || busy}
                    onClick={() => setOffset(offset + 20)}
                  >
                    Next
                  </button>
                </div>
              </section>
            ) : (
              <EmptyState
                title="Nothing saved yet"
                to="/upload"
                label="Analyze a resume"
                icon="clock"
              >
                Select “Save this analysis” during upload when you want to keep
                a private record.
              </EmptyState>
            ))
          )}
        </>
      )}
      <dialog
        ref={dialog}
        className="session-dialog"
        aria-labelledby="delete-title"
        onKeyDown={trapDialogTab}
        onCancel={(event) => {
          if (busy) event.preventDefault()
          else setSelected(null)
        }}
      >
        <h2 id="delete-title">Delete this saved analysis?</h2>
        <p>
          This permanently deletes its resume data, job descriptions, and match
          results from the application database.
        </p>
        <div className="dialog-actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => setSelected(null)}
          >
            Keep analysis
          </button>
          <button className="button danger" disabled={busy} onClick={remove}>
            {busy ? 'Deleting…' : 'Delete permanently'}
          </button>
        </div>
      </dialog>
    </>
  )
}
