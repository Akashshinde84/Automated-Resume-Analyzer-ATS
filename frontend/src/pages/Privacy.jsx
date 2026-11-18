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
            'No account required',
            'Resume analysis, matching and downloads work without login. Results remain in tab memory; closing, clearing or reloading removes them. No analytics receive resume content.',
          ],
          [
            'document',
            'Processing without saving',
            'By default, analysis and matching are stateless. Uploaded files are validated, processed in temporary storage, and removed. Extracted results and pasted job descriptions stay in the browser’s memory until cleared or reloaded.',
          ],
          [
            'clock',
            'History is disabled',
            'Anonymous requests cannot save, list, read or delete database records. Existing private records remain inaccessible. Processing creates no persistent resume history.',
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
          <strong>Clear this tab:</strong> Clear current analysis aborts pending
          requests and removes the current resume, job description and matching
          results from memory. Reloading also starts fresh.
        </p>
        <div className="inline-actions">
          <button className="button secondary" onClick={workspace.clear}>
            Clear current analysis
          </button>
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
