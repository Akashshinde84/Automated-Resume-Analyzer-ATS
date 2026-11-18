"""Anonymous stateless deployment checks using generated fictional resumes only.

Set SMOKE_API_URL and SMOKE_FRONTEND_ORIGIN in the process environment.
No credentials, resume text, report content or response bodies are printed/saved.
"""
import argparse
from io import BytesIO
import os
from urllib.parse import urlsplit

from docx import Document
import httpx
from reportlab.pdfgen import canvas


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--allow-local", action="store_true")
    local = args.parse_args().allow_local
    base = os.environ["SMOKE_API_URL"].rstrip("/")
    origin = os.environ["SMOKE_FRONTEND_ORIGIN"].rstrip("/")
    for value in (base, origin):
        url = urlsplit(value)
        assert not url.username and not url.password and not url.query and not url.fragment
        assert url.path in ("", "/")
        assert url.scheme == "https" or (local and url.hostname in {"localhost", "127.0.0.1"})
    headers = {}
    with httpx.Client(base_url=base, timeout=90, follow_redirects=False) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/v1/analyses").status_code == 403
        allowed = client.options("/api/v1/resumes/analyze", headers={"Origin": origin,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        assert allowed.headers.get("access-control-allow-origin") == origin
        denied = client.options("/api/v1/resumes/analyze", headers={"Origin": "https://untrusted.example.test",
            "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in denied.headers
        assert client.get("/api/v1/analyses", headers=headers).status_code == 403
        document = Document()
        for line in ["Name: Alex Example", "alex@example.test", "Skills", "Python, React, SQL",
                     "Experience", "Software Engineer at Example Labs", "2022 - Present", "Built Python APIs."]:
            document.add_paragraph(line)
        content = BytesIO()
        document.save(content)
        response = client.post("/api/v1/resumes/analyze", headers=headers,
            files={"file": ("synthetic.docx", content.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert response.status_code == 200
        analysis = response.json()
        assert not analysis["stored"] and analysis["id"] is None
        assert analysis["extraction"]["nlp"]["status"] == "available"
        assert "Python" in analysis["parsed"]["text"]
        jd = "Required skills: Python and SQL. Preferred skills: React and Docker. Build APIs."
        response = client.post("/api/v1/jobs/match", headers=headers,
            json={"resume": {"text": analysis["parsed"]["text"]}, "job_description": jd})
        assert response.status_code == 200
        match = response.json()
        assert 0 <= match["result"]["scores"]["overall"] <= 100
        for kind in ("json", "pdf"):
            report = client.post("/api/v1/reports", headers=headers, json={"format": kind,
                "snapshot": analysis, "match": match, "job_description": jd})
            assert report.status_code == 200
            assert report.headers.get("cache-control", "").find("no-store") >= 0
            assert report.content.startswith(b"%PDF-") if kind == "pdf" else "analysis" in report.json()
        for lines, scan in [(["Skills", "Python, SQL"], False), ([], True)]:
            content = BytesIO()
            pdf = canvas.Canvas(content)
            for i, line in enumerate(lines):
                pdf.drawString(50, 780 - 20 * i, line)
            if scan:
                from PIL import Image
                from reportlab.lib.utils import ImageReader
                pdf.drawImage(ImageReader(Image.new("RGB", (20, 20), "white")), 50, 500, 100, 100)
            pdf.showPage()
            pdf.save()
            response = client.post("/api/v1/resumes/analyze", headers=headers,
                files={"file": ("synthetic.pdf", content.getvalue(), "application/pdf")})
            assert response.status_code == 200
            assert response.json()["parsed"]["text"] == "" if scan else "Python" in response.json()["parsed"]["text"]
            if scan:
                assert response.json()["parsed"]["warnings"]
        for name, data, expected in [("broken.pdf", b"bad content", 415), ("empty.docx", b"", 422),
                                     ("wrong.exe", b"%PDF-", 415)]:
            assert client.post("/api/v1/resumes/analyze", headers=headers,
                files={"file": (name, data, "application/octet-stream")}).status_code == expected
    print("PASS: health, private-history isolation, CORS, stateless storage, DOCX/PDF/scanned extraction, NER, matching, JSON/PDF reports and invalid uploads.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, httpx.HTTPError):
        raise SystemExit("Smoke verification failed; inspect checks privately. No response content was logged.") from None
