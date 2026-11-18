import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import {
  EmptyState,
  Evidence,
  Icon,
  PageHeading,
  SafeLink,
  Warnings,
} from '../components/UI'
import { ReportDownloads } from '../components/ReportDownloads'
import { Readiness } from '../components/Readiness'

function Records({ title, items, kind }) {
  return (
    <section className="card records-card">
      <div className="card-heading">
        <h2>{title}</h2>
        <span className="count">{items.length}</span>
      </div>
      {!items.length ? (
        <p className="empty-inline">
          No {title.toLowerCase()} identified. Review the extracted text for
          missing details.
        </p>
      ) : (
        items.map((item, index) => (
          <article className="record" key={index}>
            <h3>{item[kind] || 'Not identified'}</h3>
            {(item.institution || item.company || item.issuer) && (
              <p className="record-subtitle">
                {item.institution || item.company || item.issuer}
              </p>
            )}
            {item.field && <p>{item.field}</p>}
            {item.grade && <p>Grade: {item.grade}</p>}
            {item.technologies?.length > 0 && (
              <p className="muted">
                Technologies: {item.technologies.join(', ')}
              </p>
            )}
            {(item.start_date || item.end_date || item.date) && (
              <p className="record-date">
                {item.date ||
                  [
                    item.start_date || 'Start unknown',
                    item.end_date || 'End unknown',
                  ].join(' – ')}
              </p>
            )}
            {item.description && (
              <p className="preserve-lines">{item.description}</p>
            )}
            {item.credential_id && <p>Credential: {item.credential_id}</p>}
            {(item.github_url || item.live_url) && (
              <div className="project-actions">
                {item.github_url && (
                  <SafeLink
                    value={item.github_url}
                    label="GitHub repository"
                    className="button secondary"
                  />
                )}
                {item.live_url && (
                  <SafeLink
                    value={item.live_url}
                    label="Live demo"
                    className="button secondary"
                  />
                )}
              </div>
            )}
            {item.urls
              ?.filter(
                (url) => url !== item.github_url && url !== item.live_url,
              )
              .map((url) => (
                <SafeLink key={url} value={url} />
              ))}
            <details className="evidence">
              <summary>Source text</summary>
              <p className="preserve-lines">{item.raw_text}</p>
            </details>
            <Evidence items={item.provenance} />
            <Warnings items={item.warnings} />
          </article>
        ))
      )}
    </section>
  )
}
export function Analysis() {
  const workspace = useWorkspace(),
    [category, setCategory] = useState('All')
  const analysis = workspace.analysis
  if (!analysis)
    return (
      <>
        <PageHeading
          title="Resume analysis"
          description="A structured view of the experience behind your document."
        />
        <EmptyState
          title="Your analysis starts here"
          to="/upload"
          label="Upload a resume"
        >
          Upload a resume to explore candidate details, skills, education, and
          experience.
        </EmptyState>
      </>
    )
  const { parsed, extraction } = analysis,
    candidate = extraction.candidate
  const categories = [...new Set(parsed.skills.map((skill) => skill.category))]
  const selected = parsed.skills.filter(
    (skill) => category === 'All' || skill.category === category,
  )
  return (
    <>
      <PageHeading
        eyebrow="STEP 02 / REVIEW YOUR DETAILS"
        title="Your experience, organized"
        description="Extraction is a starting point. Review the source evidence before relying on any detail."
        action={
          <Link
            className="button primary"
            to={parsed.text.trim() ? '/job' : '/upload'}
          >
            {parsed.text.trim() ? 'Compare with a job' : 'Try another resume'}
            <Icon name="arrow" />
          </Link>
        }
      />
      <div className="file-strip">
        <Icon />
        <div>
          <strong>{parsed.metadata.filename}</strong>
          <span>
            {parsed.metadata.file_type.toUpperCase()} ·{' '}
            {parsed.metadata.characters.toLocaleString()} characters
            {parsed.metadata.page_count !== null
              ? ` · ${parsed.metadata.page_count} pages`
              : ''}
          </span>
        </div>
        <span className="badge">
          {analysis.stored ? 'Saved privately' : 'In-memory only'}
        </span>
      </div>
      <Warnings items={[...parsed.warnings, ...extraction.warnings]} />
      <Readiness result={analysis.readiness} />
      {!parsed.text.trim() && (
        <div className="notice warning">
          <strong>No extractable text</strong>
          <p>
            This may be a scanned or image-only document. OCR is not enabled.
            Upload a text-based resume to continue.
          </p>
        </div>
      )}
      <div className="analysis-grid">
        <section className="card candidate-card">
          <div className="card-heading">
            <h2>Candidate details</h2>
            <span className="badge">Review required</span>
          </div>
          <div className="candidate-identity">
            <span className="avatar">
              {candidate.name
                ? Array.from(candidate.name)[0].toUpperCase()
                : '?'}
            </span>
            <div>
              <h2>{candidate.name || 'Name not identified'}</h2>
              <p className="muted">Extracted from your resume</p>
            </div>
          </div>
          <dl className="contact-list">
            <dt>Email</dt>
            <dd>
              {candidate.emails.length
                ? candidate.emails.join(', ')
                : 'Not identified'}
            </dd>
            <dt>Phone</dt>
            <dd>
              {candidate.phones.length
                ? candidate.phones.map((phone, index) => (
                    <span key={index}>
                      {phone.e164 || phone.raw}
                      {phone.extension ? ` ext. ${phone.extension}` : ''}{' '}
                      <small>({phone.status})</small>
                    </span>
                  ))
                : 'Not identified'}
            </dd>
            {[
              ['LinkedIn', candidate.linkedin_urls],
              ['GitHub', candidate.github_urls],
              ['Portfolio', candidate.portfolio_urls],
            ].map(([label, urls]) => (
              <div className="contact-row" key={label}>
                <dt>{label}</dt>
                <dd>
                  {urls.length
                    ? urls.map((url) => <SafeLink key={url} value={url} />)
                    : 'Not identified'}
                </dd>
              </div>
            ))}
          </dl>
          <Evidence
            items={candidate.provenance}
            label="How details were identified"
          />
          <p className="fine-print">
            NER:{' '}
            {extraction.nlp.status === 'available'
              ? extraction.nlp.model
              : 'Unavailable; fallback rules used'}
            . Pretrained baseline and heuristics; no custom-trained model.
          </p>
        </section>
        <section className="card skills-card">
          <div className="card-heading">
            <h2>Recognized skills</h2>
            <span className="count">{parsed.skills.length}</span>
          </div>
          <label className="sr-only" htmlFor="skill-category">
            Filter skills by category
          </label>
          <select
            id="skill-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option>All</option>
            {categories.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          {!selected.length ? (
            <p className="empty-inline">
              No ontology skills identified in this section.
            </p>
          ) : (
            <div className="skill-list">
              {selected.map((skill) => (
                <details className="skill-item" key={skill.name}>
                  <summary>
                    <span>
                      {skill.name}
                      <small>{skill.category.replaceAll('_', ' ')}</small>
                    </span>
                    <span
                      className={`badge ${skill.explicitly_listed ? 'teal' : ''}`}
                    >
                      {skill.explicitly_listed
                        ? 'Explicitly listed'
                        : 'In context'}
                    </span>
                  </summary>
                  <div className="skill-evidence">
                    {skill.occurrences.map((occurrence, index) => (
                      <p key={index}>
                        <q>{occurrence.text}</q>
                        <small>
                          {occurrence.section} · {occurrence.source_type} ·
                          characters {occurrence.start}–{occurrence.end}
                        </small>
                      </p>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}
          <p className="fine-print">
            Recognition indicates a mention, not proficiency. Open a skill to
            see its source.
          </p>
        </section>
      </div>
      <div className="records-grid">
        {candidate.summary && (
          <section className="card records-card">
            <h2>Summary</h2>
            <p>{candidate.summary}</p>
          </section>
        )}
        <Records
          title="Work experience"
          items={candidate.work_experience}
          kind="job_title"
        />
        <Records title="Education" items={candidate.education} kind="degree" />
        <Records title="Projects" items={candidate.projects} kind="name" />
        <Records
          title="Certifications"
          items={candidate.certifications}
          kind="name"
        />
        {candidate.activities?.length > 0 && (
          <Records
            title="Extracurricular activities"
            items={candidate.activities}
            kind="name"
          />
        )}
      </div>
      <section className="card source-card">
        <details>
          <summary>Review original extracted text</summary>
          <pre>{parsed.text || 'No text was extracted.'}</pre>
        </details>
      </section>
      <ReportDownloads />
      <div className="inline-actions">
        <button className="button secondary" onClick={workspace.clear}>
          Clear this session’s results
        </button>
        <p className="fine-print">
          Results are held only in this tab. Downloaded files remain on your
          device.
        </p>
      </div>
    </>
  )
}
