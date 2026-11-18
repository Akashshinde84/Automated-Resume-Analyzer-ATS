import { useState } from 'react'

export function Readiness({ result }) {
  const [priority, setPriority] = useState('all')
  if (!result) return null
  const recommendations = result.recommendations.filter(
    (item) => priority === 'all' || item.priority === priority,
  )
  return (
    <section className="readiness" aria-labelledby="readiness-title">
      <div className="readiness-overview">
        <div className="card readiness-summary">
          <p className="eyebrow">DOCUMENT QUALITY / EXPLAINED</p>
          <h2 id="readiness-title">ATS Readiness Score</h2>
          <div
            className="score-ring readiness-ring"
            style={{ '--score': `${result.score ?? 0}%` }}
            role="img"
            aria-label={`ATS readiness estimate: ${result.score === null ? 'unavailable' : `${result.score} out of 100`}`}
          >
            <div>
              <strong>
                {result.score === null ? '—' : result.score.toFixed(1)}
              </strong>
              <span>
                {result.score === null ? 'Unavailable' : 'out of 100'}
              </span>
            </div>
          </div>
          <p className="fine-print">{result.label}</p>
          <p className="fine-print">
            Independent of job matching. Rubric {result.version}.
          </p>
        </div>
        <div className="card readiness-breakdown">
          <div className="card-heading">
            <h2>Score breakdown</h2>
            <span className="badge">{result.categories.length} categories</span>
          </div>
          {result.categories.map((category) => (
            <details className="rubric-category" key={category.key}>
              <summary>
                <span>{category.label}</span>
                <strong>
                  {category.score.toFixed(1)} / {category.maximum}
                </strong>
                <progress
                  aria-label={category.label}
                  value={category.score}
                  max={category.maximum || 1}
                />
              </summary>
              {category.checks.map((check) => (
                <div className="rubric-check" key={check.code}>
                  <strong>
                    {check.label}: {check.earned.toFixed(1)} /{' '}
                    {check.maximum.toFixed(1)}
                  </strong>
                  <p>{check.reason}</p>
                  {check.evidence.map((evidence, index) => (
                    <blockquote key={index}>{evidence}</blockquote>
                  ))}
                </div>
              ))}
            </details>
          ))}
          <details className="evidence">
            <summary>Formula and limitations</summary>
            <p>{result.formula}</p>
            <ul>
              {result.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        </div>
      </div>
      <div className="card readiness-strengths">
        <h2>Resume strengths</h2>
        {result.strengths.length ? (
          <ul className="strength-list">
            {result.strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p>No strengths could be assessed from readable evidence yet.</p>
        )}
      </div>
      <div className="card readiness-improvements">
        <div className="card-heading">
          <h2>Resume improvements</h2>
          <span className="count">{result.recommendations.length}</span>
        </div>
        <p className="muted">
          Recommendations reflect this rubric. Add only facts and outcomes you
          can support.
        </p>
        <label htmlFor="improvement-priority">Filter by priority</label>
        <select
          id="improvement-priority"
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          <option value="all">All priorities</option>
          <option value="high">High priority</option>
          <option value="medium">Medium priority</option>
          <option value="low">Low priority</option>
        </select>
        {recommendations.length ? (
          recommendations.map((item) => (
            <article className="improvement-item" key={item.code}>
              <div className="improvement-meta">
                <span className={`priority priority-${item.priority}`}>
                  {item.priority} priority
                </span>
                <span>{item.section}</span>
              </div>
              <h3>{item.problem}</h3>
              <p className="muted">{item.why}</p>
              <p>{item.suggestion}</p>
              {item.possible_points !== null && (
                <small className="potential-points">
                  Up to {item.possible_points.toFixed(1)} rubric points for this
                  criterion; not guaranteed.
                </small>
              )}
              {item.evidence.length > 0 && (
                <details className="evidence">
                  <summary>Detected evidence</summary>
                  {item.evidence.map((evidence, index) => (
                    <blockquote key={index}>{evidence}</blockquote>
                  ))}
                </details>
              )}
            </article>
          ))
        ) : (
          <p>
            No recommendations in this view. Review extraction before relying on
            the score.
          </p>
        )}
      </div>
    </section>
  )
}
