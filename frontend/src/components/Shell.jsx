import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { Icon } from './UI'

const navigation = [
  ['/about', 'About', 'grid'],
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
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-mini">
            <Icon name="shield" />
            <div>
              <strong>Private by design</strong>
              <p>Processed without saving.</p>
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
            <span className="badge">Stateless analysis</span>
          </span>
          <button className="button text-button" onClick={workspace.clear}>
            Clear current analysis
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
    </div>
  )
}
