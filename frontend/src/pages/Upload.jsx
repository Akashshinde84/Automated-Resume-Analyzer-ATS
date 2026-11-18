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
    [progress, setProgress] = useState(0),
    [phase, setPhase] = useState('uploading'),
    [drag, setDrag] = useState(false),
    [region, setRegion] = useState('')
  const input = useRef(null),
    active = useRef(null)
  useEffect(() => () => active.current?.abort(), [])
  function select(files) {
    if (active.current) return
    const failure =
      files.length !== 1
        ? 'Choose one resume at a time.'
        : validateFile(files[0])
    setError(failure)
    setFile(failure ? null : files[0])
    if (!failure) analyze(files[0])
  }
  async function analyze(selected) {
    if (active.current) return
    const failure = validateFile(selected)
    if (failure || (region && !/^[A-Za-z]{2}$/.test(region))) {
      setError(failure || 'Use a two-letter phone region or leave it blank.')
      return
    }
    setBusy(true)
    setError(null)
    setProgress(0)
    setPhase('uploading')
    const control = workspace.controller()
    active.current = control
    try {
      const result = await uploadResume(selected, {
        region,
        signal: control.signal,
        onProgress: (value) => {
          setProgress(value)
          if (value === 100) setPhase('processing')
        },
      })
      if (!control.signal.aborted) {
        setPhase('results')
        await new Promise((resolve) => requestAnimationFrame(resolve))
        if (!control.signal.aborted) {
          workspace.acceptAnalysis(result)
          navigate('/analysis')
        }
      }
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      active.current = null
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="YOUR NEXT OPPORTUNITY STARTS HERE"
        title="AI Resume Analyzer"
        description="Upload your resume and get instant AI-powered insights."
      />
      <div className="upload-layout">
        <section className="card upload-card" aria-labelledby="upload-title">
          <div className="card-heading">
            <h2 id="upload-title">Upload a resume</h2>
            <span className="badge">PDF and DOCX</span>
          </div>
          <p className="muted">
            Choose a file to start analysis automatically. No account required.
          </p>
          <ErrorNotice error={error} />
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
                ? `${(file.size / 1024).toFixed(1)} KB`
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
              {file ? 'Choose another file' : 'Browse files'}
            </button>
            <small>
              PDF and DOCX / Up to {MAX_FILE_BYTES / 1024 / 1024} MB
            </small>
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
              value={region}
              onChange={(event) => setRegion(event.target.value)}
              disabled={busy}
              aria-describedby="region-help"
            />
            <small id="region-help">
              Set before uploading for local phone numbers. No country is
              assumed.
            </small>
          </div>
          {busy && (
            <div className="processing" role="status" aria-live="polite">
              <span className="spinner" />
              <div>
                <strong>
                  {phase === 'results'
                    ? 'Generating Results'
                    : phase === 'processing'
                      ? 'Extracting Text / Analyzing Skills'
                      : `Uploading${progress === null ? '' : ` ${progress}%`}`}
                </strong>
                <p>
                  Uploading ? Extracting Text ? Analyzing Skills ? Generating
                  Results
                </p>
                <small>
                  Text extraction and skill analysis run together. Please keep
                  this tab open.
                </small>
              </div>
            </div>
          )}
          <div className="form-footer">
            <span>
              <Icon name="shield" size={16} /> Original files are not retained
            </span>
            {busy ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => active.current?.abort()}
              >
                Cancel
              </button>
            ) : error && file ? (
              <button
                type="button"
                className="button primary"
                onClick={() => analyze(file)}
              >
                Retry Analysis
              </button>
            ) : null}
          </div>
        </section>
        <aside className="upload-aside">
          <div className="card guidance-card">
            <p className="eyebrow">CLEAR EVIDENCE, USEFUL INSIGHTS</p>
            <h2>Your experience, understood.</h2>
            <ul className="check-list">
              <li>
                <Icon name="check" /> Candidate details and career history
              </li>
              <li>
                <Icon name="check" /> Skills with supporting evidence
              </li>
              <li>
                <Icon name="check" /> Optional job matching and downloadable
                reports
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
            Results stay in this tab. No saved history. Review extracted details
            against your original resume.
          </p>
        </aside>
      </div>
    </>
  )
}
