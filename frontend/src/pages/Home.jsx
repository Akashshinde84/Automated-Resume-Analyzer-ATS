import { Link } from 'react-router-dom'
import { Icon } from '../components/UI'
export function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="tiny-dot" /> CLARITY FOR YOUR NEXT OPPORTUNITY
          </p>
          <h1 tabIndex="-1">
            Your experience.
            <br />A clearer <em>perspective.</em>
          </h1>
          <p className="hero-description">
            Turn your resume into structured insights. Discover the skills
            behind your experience, compare them with a role, and see the
            evidence behind every match.
          </p>
          <div className="hero-actions">
            <Link className="button primary" to="/upload">
              Analyze my resume <Icon name="arrow" />
            </Link>
            <Link className="button text-button" to="/privacy">
              <Icon name="shield" size={18} />
              How your data is handled
            </Link>
          </div>
          <p className="hero-note">
            PDF & DOCX · No automatic hiring decisions
          </p>
        </div>
        <div
          className="hero-art"
          role="img"
          aria-label="The workflow converts a resume into structured information and job comparisons"
        >
          <div className="art-orbit" />
          <div className="document-preview">
            <div className="preview-header">
              <span className="icon-tile">
                <Icon name="document" />
              </span>
              <span>
                YOUR RESUME<small>Experience, made readable</small>
              </span>
              <span className="document-dot" />
            </div>
            <div className="document-lines">
              <i />
              <i />
              <i />
            </div>
            <div className="art-section">
              <span className="art-label">01 / STRUCTURE</span>
              <h3>A complete picture</h3>
              <div className="art-tags">
                <span>Skills</span>
                <span>Education</span>
                <span>Experience</span>
              </div>
            </div>
            <div className="art-section">
              <span className="art-label">02 / COMPARE</span>
              <h3>Evidence you can explore</h3>
              <div className="art-evidence">
                <Icon name="check" size={17} />
                Resume evidence ↔ Job requirements
              </div>
            </div>
            <div className="preview-footer">
              <span className="tiny-dot" />
              Your next step starts with understanding.
            </div>
          </div>
          <div className="floating-note">
            <Icon name="shield" />
            <div>
              Privacy comes first<small>Storage is always your choice</small>
            </div>
          </div>
        </div>
      </section>
      <section className="steps-section">
        <div className="section-intro">
          <p className="eyebrow">FROM DOCUMENT TO DIRECTION</p>
          <h2>Three steps. A more informed next move.</h2>
        </div>
        <div className="feature-grid">
          {[
            [
              '01',
              'upload',
              'Bring your experience',
              'Upload a text-based PDF or DOCX. Review extracted details, skills, and source text.',
            ],
            [
              '02',
              'target',
              'Add the opportunity',
              'Paste a job description to identify required and preferred skills using a shared ontology.',
            ],
            [
              '03',
              'document',
              'Explore the evidence',
              'Understand skill coverage and text similarity, with grounded suggestions you can review.',
            ],
          ].map(([number, icon, title, description]) => (
            <article className="feature-card" key={number}>
              <div className="feature-top">
                <span className="icon-tile">
                  <Icon name={icon} />
                </span>
                <span>{number}</span>
              </div>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>
      <div className="home-bottom">
        <Icon name="shield" />
        <p>
          <strong>Useful insight, with clear limits.</strong> Extraction can
          miss details. Match scores are project-defined compatibility
          estimates, never hiring probabilities.
        </p>
        <Link to="/upload">
          Get started <Icon name="arrow" size={18} />
        </Link>
      </div>
    </>
  )
}
