import { Link } from 'react-router-dom'
import { useWorkspace } from '../context/Workspace'
import { Icon, PageHeading } from '../components/UI'
export function Privacy() {
  const workspace = useWorkspace()
  return (
    <>
      <PageHeading
        eyebrow="YOUR DATA / YOUR CHOICE"
        title="Privacy, made clear"
        description="Resumes contain personal information. Here’s what this workspace does with it."
      />
      <div className="privacy-grid">
        {[
          [
            'shield',
            'Private access',
            'The API requires the backend owner’s access token. This first deployment is a single-user workspace, not a public candidate portal. Your token is held in this tab’s memory, never in browser storage or build-time variables.',
          ],
          [
            'document',
            'Processing without saving',
            'By default, analysis and matching are stateless. Uploaded files are validated, processed in temporary storage, and removed. Extracted results and pasted job descriptions stay in the browser’s memory until cleared or reloaded.',
          ],
          [
            'clock',
            'Optional saved history',
            'Saving is available only when the authenticated backend confirms persistence is enabled. You must opt in separately for an analysis and a match. Saved records include extracted personal information; saved matches also include the job description. The backend controls retention, and saved records show their expiration.',
          ],
        ].map(([icon, title, text]) => (
          <article className="card privacy-card" key={title}>
            <span className="icon-tile">
              <Icon name={icon} />
            </span>
            <h2>{title}</h2>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <section className="card privacy-detail">
        <h2>Clear or delete your data</h2>
        <p>
          <strong>Clear this tab:</strong> Disconnect to abort pending requests
          and remove the token, current resume, job description, and match
          results from application memory. Closing or reloading the tab also
          starts a fresh session. This does not delete saved records.
        </p>
        <p>
          <strong>Delete saved records:</strong> Open saved history, select
          Delete, and confirm. The backend removes the analysis and its related
          structured data, job descriptions, and matches together. Hosting
          providers and database backups may have their own retention policies;
          contact the deployment owner about those.
        </p>
        <div className="inline-actions">
          {workspace.token && (
            <button className="button secondary" onClick={workspace.disconnect}>
              Disconnect & clear session
            </button>
          )}
          {workspace.historyAvailable && (
            <Link className="button primary" to="/history">
              Manage saved history
              <Icon name="arrow" />
            </Link>
          )}
        </div>
        <hr />
        <h2>Downloaded reports</h2>
        <p>
          JSON and PDF reports contain personal information from the current
          authorized analysis. Report generation does not save another server
          copy. Keep downloaded files private: deleting a server record or
          clearing this tab does not remove copies already downloaded to your
          device.
        </p>
        <h2>Understand the limits</h2>
        <p>
          OCR is not enabled. Scanned PDFs may produce no text. Regex,
          heuristics, and pretrained NER can miss or misidentify candidate
          information. Recognized skills indicate mentions, not verified
          proficiency.
        </p>
        <p>
          Matching uses ontology skill coverage and lexical TF-IDF similarity.
          The score is a project-defined compatibility estimate, not an ATS
          score, hiring probability, or hiring decision. Review every result
          against the source documents.
        </p>
        <p className="fine-print">
          Use HTTPS for a deployed frontend and API. The deployment owner must
          configure restricted CORS origins, retention cleanup, secure database
          access, and provider logging policies. This frontend does not send
          resume content to analytics or paid AI services.
        </p>
      </section>
    </>
  )
}
