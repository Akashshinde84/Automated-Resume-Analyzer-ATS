import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { MAX_FILE_BYTES, uploadResume, validateFile } from '../lib/api'
import { ErrorNotice, Icon, PageHeading } from '../components/UI'

export function Upload() {
  const workspace = useWorkspace(),
    navigate = useNavigate()
  const [file, setFile] = useState(null),
    [error, setError] = useState(null),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(null),
    [drag, setDrag] = useState(false),
    [store, setStore] = useState(false),
    [region, setRegion] = useState('')
  const input = useRef(null),
    active = useRef(null)
  useEffect(() => () => active.current?.abort(), [])
  function select(files) {
    if (busy) return
    const failure =
      files.length !== 1
        ? 'Choose one resume at a time.'
        : validateFile(files[0])
    setError(failure)
    setFile(failure ? null : files[0])
  }
  async function submit(event) {
    event.preventDefault()
    const failure = validateFile(file)
    if (failure) {
      setError(failure)
      return
    }
    if (!workspace.token) {
      workspace.setSessionOpen(true)
      return
    }
    setBusy(true)
    setError(null)
    setProgress(0)
    const control = workspace.controller()
    active.current = control
    try {
      const result = await uploadResume(file, workspace.token, {
        store: store && workspace.historyAvailable,
        region,
        onProgress: setProgress,
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
  return (
    <>
      <PageHeading
        eyebrow="STEP 01 / YOUR EXPERIENCE"
        title="Start with your resume"
        description="A document is all you need. We’ll organize the details so you can review them."
      />
      <div className="upload-layout">
        <form className="card upload-card" onSubmit={submit}>
          <div className="card-heading">
            <h2>Upload a resume</h2>
            <span className="badge">PDF or DOCX</span>
          </div>
          <ErrorNotice error={error} />
          {error?.status === 0 && store && (
            <p className="notice warning">
              The request may have completed on the server. Check private
              history before retrying to avoid saving a duplicate analysis.
            </p>
          )}
          <div
            className={`dropzone ${drag ? 'dragging' : ''}`}
            onDragOver={(event) => {
              event.preventDefault()
              if (!busy) setDrag(true)
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDrag(false)
              select(event.dataTransfer.files)
            }}
          >
            <span className="upload-symbol">
              <Icon name={file ? 'document' : 'upload'} size={32} />
            </span>
            <h3>{file ? file.name : 'Drop your resume here'}</h3>
            <p>
              {file
                ? `${(file.size / 1024).toFixed(1)} KB · Ready to analyze`
                : 'or choose a file from your device'}
            </p>
            <input
              ref={input}
              className="sr-only"
              id="resume-file"
              type="file"
              accept=".pdf,.docx"
              disabled={busy}
              onChange={(event) => {
                if (event.target.files.length) select(event.target.files)
                event.target.value = ''
              }}
              aria-label="Choose PDF or DOCX resume"
            />
            <button
              className="button secondary"
              type="button"
              disabled={busy}
              onClick={() => input.current.click()}
            >
              {file ? 'Change file' : 'Browse files'}
            </button>
            <small>PDF or DOCX · Up to {MAX_FILE_BYTES / 1024 / 1024} MB</small>
          </div>
          <div className="field">
            <label htmlFor="region">
              Phone region <span className="optional">optional</span>
            </label>
            <input
              id="region"
              className="region-input"
              placeholder="e.g. GB"
              maxLength={2}
              pattern="[A-Za-z]{2}"
              value={region}
              onChange={(event) => setRegion(event.target.value)}
              disabled={busy}
              aria-describedby="region-help"
            />
            <small id="region-help">
              Two-letter country code for local phone numbers. No country is
              assumed.
            </small>
          </div>
          {workspace.historyAvailable && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={store}
                onChange={(event) => setStore(event.target.checked)}
                disabled={busy}
              />
              <span>
                Save this analysis to private history
                <small>
                  Includes extracted personal information. You can delete it
                  later.
                </small>
              </span>
            </label>
          )}
          {busy && (
            <div className="processing" role="status" aria-live="polite">
              <span className="spinner" />
              <div>
                <strong>
                  {progress !== null && progress < 100
                    ? `Uploading… ${progress}%`
                    : 'Analyzing your resume…'}
                </strong>
                <p>
                  {progress === 100
                    ? 'Extracting text, candidate details, and skills. Please keep this tab open.'
                    : 'Sending your file securely to the configured backend.'}
                </p>
              </div>
            </div>
          )}
          <div className="form-footer">
            <span>
              <Icon name="shield" size={16} />
              Original files are not retained
            </span>
            {busy ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => active.current?.abort()}
              >
                Cancel
              </button>
            ) : (
              <button className="button primary" disabled={!file}>
                {workspace.token ? 'Analyze resume' : 'Connect to analyze'}
                <Icon name="arrow" />
              </button>
            )}
          </div>
        </form>
        <aside className="upload-aside">
          <div className="card guidance-card">
            <p className="eyebrow">A BETTER EXTRACTION</p>
            <h2>Keep it readable.</h2>
            <ul className="check-list">
              <li>
                <Icon name="check" />
                Use a text-based PDF or DOCX.
              </li>
              <li>
                <Icon name="check" />
                Include clear section headings.
              </li>
              <li>
                <Icon name="check" />
                Review uncertain or missing details.
              </li>
            </ul>
            <div className="notice quiet">
              <strong>Scanned resume?</strong>
              <p>
                Image-only PDFs cannot be read yet. Export a text-based copy;
                OCR is not enabled.
              </p>
            </div>
          </div>
          <p className="aside-note">
            The server checks file signatures and enforces its own size limit.
            Client checks help you catch problems sooner.
          </p>
        </aside>
      </div>
    </>
  )
}
