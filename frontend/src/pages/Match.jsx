import { Link } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { scoreLabel } from '../lib/api'
import { ReportDownloads } from '../components/ReportDownloads'
import {
  EmptyState,
  Evidence,
  Icon,
  PageHeading,
  Warnings,
} from '../components/UI'
function SkillComparison({ title, items, empty, tone = '' }) {
  return (
    <section className="card comparison-card">
      <div className="card-heading">
        <h2>{title}</h2>
        <span className={`count ${tone}`}>{items.length}</span>
      </div>
      {items.length ? (
        items.map((skill) => (
          <article className="comparison-item" key={skill.name}>
            <div>
              <strong>{skill.name}</strong>
              <span className="badge">
                {skill.importance}
                {typeof skill.matched === 'boolean'
                  ? ` · ${skill.matched ? 'Found' : 'Not found'}`
                  : ''}
              </span>
            </div>
            <Evidence items={skill.resume_evidence} label="Resume evidence" />
            <Evidence
              items={skill.job_evidence}
              label="Job requirement evidence"
            />
          </article>
        ))
      ) : (
        <p className="empty-inline">{empty}</p>
      )}
    </section>
  )
}
export function Match() {
  const { match } = useWorkspace()
  if (!match)
    return (
      <>
        <PageHeading title="Match results" />
        <EmptyState
          title="A clearer comparison awaits"
          to="/job"
          label="Add a job description"
          icon="target"
        >
          Compare your analyzed resume with a job description to see real scores
          and evidence.
        </EmptyState>
      </>
    )
  const result = match.result,
    value = result.scores.overall
  return (
    <>
      <PageHeading
        eyebrow="YOUR OPPORTUNITY / EXPLAINED"
        title="See how your experience aligns"
        description="Explore the overlap, review the gaps, and decide what deserves a closer look."
        action={
          <Link className="button secondary" to="/job">
            Edit job description
            <Icon name="arrow" />
          </Link>
        }
      />
      <Warnings items={result.warnings} />
      <div className="score-layout">
        <section className="card overall-card">
          <div
            className="score-ring"
            style={{
              '--score': typeof value === 'number' ? `${value}%` : '0%',
            }}
            role="img"
            aria-label={`Overall compatibility estimate: ${scoreLabel(value)}`}
          >
            <div>
              <strong>
                {typeof value === 'number' ? value.toFixed(1) : '—'}
              </strong>
              <span>
                {typeof value === 'number' ? 'out of 100' : 'Unavailable'}
              </span>
            </div>
          </div>
          <div>
            <p className="eyebrow">SEPARATE FROM ATS READINESS</p>
            <h2>Job Match Score</h2>
            <p className="muted">{result.score_meaning}</p>
            <span className="badge">
              {match.stored ? 'Comparison saved' : 'In-memory comparison'}
            </span>
          </div>
        </section>
        <div className="component-scores">
          <section className="card metric-card">
            <span>Skill coverage</span>
            <strong>{scoreLabel(result.scores.skill_overlap)}</strong>
            <p>
              Coverage of recognized job skills, weighted by requirement
              importance.
            </p>
          </section>
          <section className="card metric-card">
            <span>Text similarity</span>
            <strong>{scoreLabel(result.scores.text_similarity)}</strong>
            <p>
              TF-IDF cosine similarity over supported professional terms. This
              is lexical similarity.
            </p>
          </section>
        </div>
      </div>
      {result.supporting_records?.length > 0 && (
        <section className="card records-card supporting-records">
          <h2>Projects and experience supporting this match</h2>
          {result.supporting_records.map((record, index) => (
            <article className="record" key={index}>
              <h3>{record.name || 'Untitled record'}</h3>
              <p className="muted">
                {record.section} · {record.skills.join(', ')}
              </p>
              <Evidence
                items={record.evidence}
                label="Supporting skill evidence"
              />
            </article>
          ))}
        </section>
      )}
      <details className="card score-explanation">
        <summary>How this estimate is calculated</summary>
        <p className="preserve-lines">{result.formula}</p>
        <dl className="weight-list">
          {Object.entries(result.effective_weights).map(([key, weight]) => (
            <div key={key}>
              <dt>{key} effective weight</dt>
              <dd>{(weight * 100).toFixed(1)}%</dd>
            </div>
          ))}
        </dl>
        <p className="fine-print">{result.method}</p>
        <p className="fine-print">
          Required / preferred / unspecified skill importance:{' '}
          {result.weights.required_importance} /{' '}
          {result.weights.preferred_importance} /{' '}
          {result.weights.unspecified_importance}. Ontology{' '}
          {result.ontology_version}.
        </p>
      </details>
      <div className="comparison-grid">
        <SkillComparison
          title="Matched skills"
          items={result.matched_skills}
          tone="teal"
          empty="No supported skill overlap was found."
        />
        <SkillComparison
          title="Missing required skills"
          items={result.missing_required_skills}
          empty="No missing required ontology skills were identified. Review the full job description for other requirements."
        />
        <SkillComparison
          title="Preferred skills"
          items={result.preferred_skills}
          empty="No preferred ontology skills were identified."
        />
        <SkillComparison
          title="Other mentioned skills"
          items={result.unspecified_skills}
          empty="No additional unclassified job skills were identified."
        />
      </div>
      <section className="card suggestions-card">
        <div className="card-heading">
          <h2>Your next steps</h2>
          <Icon name="target" />
        </div>
        <p className="muted">
          Suggestions are grounded in the resume and job description. Add a
          qualification only when it is true and supported by your experience.
        </p>
        {result.suggestions.length ? (
          result.suggestions.map((suggestion, index) => (
            <article
              className="suggestion"
              key={`${suggestion.code}-${suggestion.skill}`}
            >
              <span>{String(index + 1).padStart(2, '0')}</span>
              <div>
                <h3>{suggestion.skill}</h3>
                {suggestion.priority && (
                  <div className="improvement-meta">
                    <span
                      className={`priority priority-${suggestion.priority}`}
                    >
                      {suggestion.priority} priority
                    </span>
                    <span>{suggestion.section}</span>
                  </div>
                )}
                {suggestion.problem && (
                  <p>
                    <strong>{suggestion.problem}</strong>
                  </p>
                )}
                {suggestion.why && <p className="muted">{suggestion.why}</p>}
                <p>{suggestion.message}</p>
                <Evidence items={suggestion.resume_evidence} />
              </div>
            </article>
          ))
        ) : (
          <p className="empty-inline">
            No evidence-based suggestions are available for this comparison.
          </p>
        )}
      </section>
      {result.shared_text_features.length > 0 && (
        <details className="card source-card">
          <summary>Shared professional text features</summary>
          <div className="tag-cloud">
            {result.shared_text_features.map((item) => (
              <span className="badge" key={item.feature}>
                {item.feature} · {item.kind}
              </span>
            ))}
          </div>
        </details>
      )}
      <ReportDownloads includeMatch />
    </>
  )
}
