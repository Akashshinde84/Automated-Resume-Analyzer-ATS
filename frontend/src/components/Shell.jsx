import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { API_BASE, ApiError, request } from '../lib/api'
import { ErrorNotice, Icon, trapDialogTab } from './UI'

function SessionDialog() {
  const workspace = useWorkspace()
  const dialog = useRef(null)
  const pending = useRef(null)
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)
  useEffect(() => {
    if (workspace.sessionOpen) dialog.current.showModal()
    else {
      dialog.current.close()
      pending.current?.abort()
    }
  }, [workspace.sessionOpen])
  function close() {
    pending.current?.abort()
    setValue('')
    setError(null)
    setHealth(null)
    workspace.setSessionOpen(false)
  }
  async function checkHealth() {
    setBusy(true)
    setError(null)
    setHealth(null)
    const control = workspace.controller()
    pending.current = control
    try {
      const result = await request('/health', '', { signal: control.signal })
      if (result.status !== 'ok')
        throw new ApiError('The API returned an unexpected health response.')
      if (!control.signal.aborted)
        setHealth(
          'API is reachable. Connect with your private token to access analyses.',
        )
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      setBusy(false)
    }
  }
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const control = workspace.controller()
    pending.current = control
    try {
      await workspace.connect(value.trim(), control.signal)
      setValue('')
    } catch (failure) {
      if (failure.name !== 'AbortError') setError(failure)
    } finally {
      workspace.release(control)
      setBusy(false)
    }
  }
  return (
    <dialog
      ref={dialog}
      className="session-dialog"
      aria-labelledby="session-title"
      onKeyDown={trapDialogTab}
      onCancel={close}
      onClose={() => workspace.setSessionOpen(false)}
    >
      <button
        className="icon-button dialog-close"
        aria-label="Close connection settings"
        onClick={close}
      >
        <Icon name="close" />
      </button>
      <span className="icon-tile">
        <Icon name="shield" />
      </span>
      <h2 id="session-title">Connect your private workspace</h2>
      <p className="muted">
        Use the owner access token configured on your FastAPI backend. It stays
        in this tab’s memory and is cleared when you disconnect or reload.
      </p>
      <p className="endpoint">
        API endpoint <code>{API_BASE}</code>
      </p>
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <label htmlFor="token">Private access token</label>
        <input
          id="token"
          type="password"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          required
          disabled={busy}
          aria-describedby="token-help"
        />
        <small id="token-help">
          Never put this token in VITE_ variables or share it with other users.
        </small>
        <button
          className="button primary full"
          disabled={busy || !value.trim()}
        >
          {busy ? 'Verifying connection…' : 'Connect securely'}
        </button>
      </form>
      <button
        className="button text-button full"
        disabled={busy}
        onClick={checkHealth}
      >
        Check API health
      </button>
      {health && (
        <p className="fine-print" role="status">
          {health}
        </p>
      )}
    </dialog>
  )
}
const navigation = [
  ['/', 'Overview', 'grid'],
  ['/upload', 'Upload resume', 'upload'],
  ['/analysis', 'Resume analysis', 'document'],
  ['/job', 'Job description', 'target'],
  ['/match', 'Match results', 'target'],
]
export function Shell() {
  const workspace = useWorkspace()
  const [menu, setMenu] = useState(false)
  const location = useLocation()
  useEffect(() => {
    const heading = document.querySelector('main h1')
    document.title = `${heading?.textContent || 'Workspace'} · Resume Atlas`
    heading?.focus()
    window.scrollTo(0, 0)
  }, [location.pathname])
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="mobile-header">
        <Link className="brand" to="/">
          <span className="brand-mark">
            <Icon />
          </span>
          Resume<span>Atlas</span>
        </Link>
        <button
          className="icon-button"
          aria-label="Toggle navigation"
          aria-expanded={menu}
          aria-controls="workspace-nav"
          onClick={() => setMenu(!menu)}
        >
          <Icon name={menu ? 'close' : 'menu'} />
        </button>
      </header>
      <aside className={`sidebar ${menu ? 'is-open' : ''}`}>
        <Link className="brand desktop-brand" to="/">
          <span className="brand-mark">
            <Icon />
          </span>
          Resume<span>Atlas</span>
        </Link>
        <p className="nav-label">WORKSPACE</p>
        <nav id="workspace-nav" aria-label="Main navigation">
          {navigation.map(([to, label, icon]) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMenu(false)}
            >
              <Icon name={icon} />
              {label}
            </NavLink>
          ))}
          {workspace.historyAvailable && (
            <NavLink to="/history" onClick={() => setMenu(false)}>
              <Icon name="clock" />
              Saved history
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-mini">
            <Icon name="shield" />
            <div>
              <strong>Private by design</strong>
              <p>Save only when you choose.</p>
            </div>
          </div>
          <NavLink to="/privacy" onClick={() => setMenu(false)}>
            Privacy & deletion <Icon name="arrow" size={16} />
          </NavLink>
          <small>Built for insight. Decisions stay human.</small>
        </div>
      </aside>
      <div className="workspace">
        <div className="topbar">
          <span className="topbar-label">
            RESUME INTELLIGENCE{' '}
            <span className="badge">Personal workspace</span>
          </span>
          <button
            className={`connection-button ${workspace.token ? 'connected' : ''}`}
            onClick={() =>
              workspace.token
                ? workspace.disconnect()
                : workspace.setSessionOpen(true)
            }
          >
            <span className="status-dot" />
            {workspace.token ? 'Disconnect & clear session' : 'Connect backend'}
          </button>
        </div>
        <main id="main-content">
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>Resume Atlas · Understand your experience.</span>
          <Link to="/privacy">
            Your data, your choice <Icon name="shield" size={14} />
          </Link>
        </footer>
      </div>
      <SessionDialog />
    </div>
  )
}
