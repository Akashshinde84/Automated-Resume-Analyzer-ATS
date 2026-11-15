# Phase 9 security review


- Corrupt/encrypted PDFs, scanned/image-only PDFs, empty documents, fake extensions,
  invalid request content types, spoofed per-file MIME, 10 MiB+ uploads, bounded
  chunked bodies and DOCX expansion are exercised. Per-file MIME is untrusted:
  genuine signed PDF/DOCX content can be accepted despite a false MIME label;
  a PDF MIME label cannot make HTML/executable content valid.
- Successful/failed uploads clean temporary paths; traversal filenames never
  become local paths. DOCX external XML entities are not resolved. HTML/links in
  reports are escaped, not executed or fetched. Regex/pathological-input checks
  supplement existing matching/parser regressions.
- Invalid tokens fail closed before processing. CORS rejects unapproved origins;
  explicit allowed hosts, no-store headers, owner checks, expiration and cascading
  deletion pass. Saved report IDs cannot cross analysis/owner boundaries; signed
  snapshots resist tampering. No multi-user mode is enabled.
- Exception/upload tests verify private contact strings do not appear in logs or
  error responses. SQL engines use `echo=False` and `hide_parameters=True`;
  retention warnings use constant messages. Hosted proxy/database logs were not
  inspected and need operator review.
- Fixed measured low-contrast text in headings, evidence, suggestions, guidance and
  the landing illustration. Added explicit Tab/Shift-Tab wrapping for both dialogs;
  real keyboard checks now pass.
- The first Python audit reported 25 advisory entries in pip 24.2 and QA-installed
  filelock 3.32.7. Updated to pip **26.3** and filelock **4.2.10**; final audit is
  clean for auditable distributions. CI upgrades pip and requires patched filelock.
  Registry timeouts were retried without bypassing TLS or ignoring advisories.
- The source secret guard reads only Git-visible files, not ignored `.env`, uploads,
  caches or virtual environments, and never prints matched values. No deployment
  credentials were created or read. Disposable CI database credentials and synthetic
  test tokens are not production secrets. Regex scanning is not exhaustive.


See [QA/release decision](qa-report.md) for checks that remain unverified.
