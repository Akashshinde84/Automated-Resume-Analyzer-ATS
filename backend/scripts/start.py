"""Production entry point: no reload, one model copy, no personal access logs."""
import os
from pathlib import Path
import sys
import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
                workers=1, access_log=False, proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                timeout_keep_alive=5, limit_concurrency=32)
