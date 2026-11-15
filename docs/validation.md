# Phase 1 validation

Validated on 2026-11-15 in Windows PowerShell.

## Results

- Backend: **2 passed**, covering health response and configured CORS origin handling.
- Frontend: **production build passed**, Vite 7.3.8, 42 modules transformed.
- npm installation: 83 packages added; npm reported zero vulnerabilities.
- Git initialized; no commit, remote, GitHub repository, or deployment created.
- Ignore rules checked for secrets, virtual environment, node_modules, dist,
  uploads, resumes, temporary files, and pytest caches.

## Commands executed

Inspection: `Get-Location`, `rg --files`, `Get-ChildItem -Force`,
`python --version`, `py -0p`, `node --version`, `npm --version`,
`npm config get registry`, and `git status --short`.

Installation and verification:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m ensurepip --upgrade --default-pip
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
npm --prefix frontend install
Push-Location backend
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
Pop-Location
npm --prefix frontend run build
git init
git status --short
git ls-files --others --exclude-standard
```

`git check-ignore` was also used against representative private and generated
paths. Installation was retried after sandbox permission errors; backend install
and Vite build required elevated execution for temporary files and subprocesses.
No global Python packages were installed.

## Fixes and limits

- Windows command shims failed on the workspace's ampersand. Package scripts now
  invoke Vite through Node directly.
- Removed a UTF-8 BOM introduced during a PowerShell package.json edit.
- Python 3.11 is unavailable on this machine. Tests ran with Python 3.12.6;
  Python 3.11 validation remains outstanding. Setup instructions target 3.11.
- The installed Starlette TestClient emits an HTTPX deprecation warning. It does
  not fail the tests. A sandbox pytest cache warning was avoided on the final run
  using `-p no:cacheprovider`.
- Browser interaction testing and actual hosting were not performed.
- No later-phase functionality was implemented.
