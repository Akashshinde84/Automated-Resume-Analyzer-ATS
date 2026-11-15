import { Component } from 'react'
import { Link } from 'react-router-dom'
import { safeUrl } from '../lib/api'

export function trapDialogTab(event) {
  if (event.key !== 'Tab') return
  const dialog = event.currentTarget
  const controls = [
    ...dialog.querySelectorAll(
      'button, input, select, textarea, a[href], [tabindex]',
    ),
  ].filter(
    (element) =>
      !element.disabled &&
      element.tabIndex >= 0 &&
      element.getClientRects().length,
  )
  const first = controls[0],
    last = controls.at(-1)
  if (!first) {
    event.preventDefault()
    return
  }
  if (
    !dialog.contains(document.activeElement) ||
    (!event.shiftKey && document.activeElement === last)
  ) {
    event.preventDefault()
    first.focus()
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  }
}

export function Icon({ name = 'document', size = 20, ...props }) {
  const paths = {
    document:
      'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h5',
    upload: 'M12 16V3 M7 8l5-5 5 5 M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4',
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    target: 'M21 12a9 9 0 1 1-9-9 M17 12a5 5 0 1 1-5-5 M12 12l9-9 M16 3h5v5',
    shield: 'M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6z M8 12l3 3 5-6',
    clock: 'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
    arrow: 'M5 12h14 M13 6l6 6-6 6',
    check: 'M5 12l4 4L19 6',
    menu: 'M4 6h16 M4 12h16 M4 18h16',
    close: 'M6 6l12 12 M6 18L18 6',
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name] || paths.document} />
    </svg>
  )
}
export function PageHeading({
  eyebrow = 'YOUR WORKSPACE',
  title,
  description,
  action,
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 tabIndex="-1">{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {action}
    </header>
  )
}
export function EmptyState({ title, children, to, label, icon = 'document' }) {
  return (
    <div className="empty-state card">
      <span className="icon-tile">
        <Icon name={icon} size={30} />
      </span>
      <h2>{title}</h2>
      <p className="muted">{children}</p>
      {to && (
        <Link className="button primary" to={to}>
          {label}
          <Icon name="arrow" />
        </Link>
      )}
    </div>
  )
}
export function ErrorNotice({ error }) {
  if (!error) return null
  return (
    <div className="notice error" role="alert">
      <strong>Something needs attention</strong>
      <p>{typeof error === 'string' ? error : error.message}</p>
    </div>
  )
}
export function Warnings({ items = [] }) {
  const warnings = [...new Set(items)]
  return (
    warnings.length > 0 && (
      <div className="notice warning">
        <strong>Review extraction notes</strong>
        <ul>
          {warnings.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    )
  )
}
export function Skeleton({ label = 'Loading your analysis…' }) {
  return (
    <div role="status" aria-live="polite" className="skeleton-wrap">
      <span className="sr-only">{label}</span>
      {[1, 2, 3].map((item) => (
        <div key={item} className="skeleton card" />
      ))}
    </div>
  )
}
export function SafeLink({ value }) {
  const href = safeUrl(value)
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {value}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  ) : (
    <span>{value}</span>
  )
}
export function Evidence({ items = [], label = 'View supporting evidence' }) {
  return (
    items.length > 0 && (
      <details className="evidence">
        <summary>{label}</summary>
        {items.map((item, index) => (
          <blockquote key={index}>
            {item.context || item.source_text || item.text}
            <small>
              {item.section || item.method}
              {item.confidence ? ` · ${item.confidence} rule confidence` : ''}
            </small>
          </blockquote>
        ))}
      </details>
    )
  )
}
export class ErrorBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <main className="fatal card">
        <h1>The workspace could not render</h1>
        <p>
          Reload to start a fresh private session. Unsaved information will be
          cleared.
        </p>
        <button
          className="button primary"
          onClick={() => window.location.reload()}
        >
          Reload workspace
        </button>
      </main>
    ) : (
      this.props.children
    )
  }
}
