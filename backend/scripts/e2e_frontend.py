"""Run real React + FastAPI browser tests against disposable synthetic data only.

From repository root: backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
Requires frontend npm dependencies and `playwright install chromium` beforehand.
No user environment file, database or uploaded candidate file is modified.
"""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from alembic import command
from alembic.config import Config
from docx import Document
import httpx
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@contextmanager
def disposable_directory(root):
    temporary = TemporaryDirectory(prefix="phase8-e2e-", dir=root)
    target = Path(temporary.name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise RuntimeError("Unexpected test workspace path.")
    try:
        yield target
    finally:
        # Windows can briefly retain SQLite handles after an owned process tree
        # exits. Retry this verified disposable directory, never another path.
        for attempt in range(20):
            try:
                temporary.cleanup()
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.2)


def fixtures(directory):
    lines = ["Name: Sofía Rivera", "sofia@example.test", "Summary", "Builds reliable APIs.",
             "Technical Skills", "Python, SQL, React", "Professional Experience", "Software Engineer at Example Labs",
             "Jan 2022 - Present", "Built Python APIs and SQL data pipelines.", "Education", "Example University",
             "Bachelor of Science in Computer Science", "2017 - 2021", "Projects", "Resume Platform", "Built a React dashboard."]
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(directory / "synthetic.docx")
    pdf = canvas.Canvas(str(directory / "synthetic.pdf"))
    y = 800
    for line in lines:
        pdf.drawString(48, y, line.replace("í", "i"))
        y -= 23
    pdf.save()
    image = Image.new("RGB", (200, 200), "white")
    scan = canvas.Canvas(str(directory / "scan.pdf"))
    scan.drawImage(ImageReader(image), 40, 500, width=200, height=200)
    scan.save()


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js 22.12+ is required.")
    frontend = ROOT / "frontend"
    tmp_root = ROOT / ".tmp"
    tmp_root.mkdir(exist_ok=True)
    # Screenshots/downloads are synthetic, ignored, and retained for visual QA.
    output = tmp_root / "phase8-e2e-results"
    with disposable_directory(tmp_root) as directory:
        fixtures(directory)
        url = "sqlite:///" + (directory / "isolated.db").as_posix()
        config = Config(str(BACKEND / "alembic.ini"))
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        api_port, ui_port = port(), port()
        while api_port == ui_port:
            ui_port = port()
        base = f"http://127.0.0.1:{ui_port}"
        api = f"http://127.0.0.1:{api_port}"
        environment = {**os.environ, "APP_MODE": "single_user", "SINGLE_USER_API_KEY": secrets.token_urlsafe(48),
            "SINGLE_USER_ID": "phase8-test-owner", "STORAGE_ENABLED": "true", "DATABASE_URL": url,
            "REQUIRE_NER_MODEL": "false", "SPACY_MODEL": "en_core_web_sm", "RETENTION_DAYS": "7",
            "ALLOWED_HOSTS": '["localhost","127.0.0.1"]', "CORS_ORIGINS": json.dumps([base]),
            "VITE_API_BASE_URL": api, "VITE_MAX_UPLOAD_MB": "10", "E2E_BASE_URL": base,
            "E2E_FILES_DIR": str(directory), "E2E_OUTPUT_DIR": str(output), "NO_COLOR": "1"}
        environment["E2E_OWNER_TOKEN"] = environment["SINGLE_USER_API_KEY"]
        processes = []
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"],
                cwd=BACKEND, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
            processes.append(subprocess.Popen([node, "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(ui_port), "--strictPort"],
                cwd=frontend, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
            deadline = time.monotonic() + 45
            with httpx.Client(timeout=2) as client:
                while True:
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError("An isolated test server exited before readiness.")
                    try:
                        if client.get(api + "/health").status_code == 200 and client.get(base).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Isolated test servers did not become ready.")
                    time.sleep(.2)
            result = subprocess.run([node, "node_modules/@playwright/test/cli.js", "test"], cwd=frontend, env=environment)
            return result.returncode
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    if os.name == "nt":
                        # Kill only process trees launched by this run (venv launchers
                        # and esbuild can have children on Windows).
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        process.terminate()
                    process.wait(timeout=15)


if __name__ == "__main__":
    raise SystemExit(main())
