"""Short-lived snapshot integrity receipts; no resume content is stored here.

Anonymous reports require the complete signed snapshot, never a database ID.
Legacy owner-mode receipts use a separate domain and still require owner access.
"""
import base64
import hashlib
import hmac
import json
import time


class InvalidReportSnapshot(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def analysis_data(value):
    # Exclude history pagination and every saved comparison, even for AnalysisDetail.
    return value.model_dump(mode="json", include={"id", "stored", "created_at", "expires_at", "parsed", "extraction", "readiness"})


def match_data(value):
    return value.model_dump(mode="json", exclude={"report_token"})


class ReportReceipts:
    def __init__(self, settings):
        key = settings.single_user_api_key.get_secret_value() if settings.single_user_api_key else ""
        if not settings.report_signing_key or not settings.report_signing_key.get_secret_value():
            raise RuntimeError("Report signing is not initialized.")
        context = (b"resume-report-anonymous-v1" if settings.app_mode == "anonymous" else
                   b"resume-report-v1:" + settings.single_user_id.encode() + b":" + hashlib.sha256(key.encode()).digest())
        self.key = hmac.digest(settings.report_signing_key.get_secret_value().encode(), context, "sha256")
        self.ttl = settings.report_token_ttl_seconds

    def issue(self, purpose, data):
        now = int(time.time())
        payload = canonical({"v": 1, "purpose": purpose, "digest": digest(data), "issued": now, "expires": now + self.ttl})
        encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
        signature = hmac.digest(self.key, encoded, "sha256").hex()
        return encoded.decode() + "." + signature

    def verify(self, token, purpose, data):
        try:
            encoded, signature = (token or "").split(".")
            expected = hmac.digest(self.key, encoded.encode("ascii"), "sha256").hex()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            now = int(time.time())
            if (payload["v"] != 1 or payload["purpose"] != purpose or payload["digest"] != digest(data)
                    or not payload["issued"] <= now <= payload["expires"]
                    or payload["expires"] - payload["issued"] > self.ttl):
                raise ValueError()
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise InvalidReportSnapshot() from None

    def sign_analysis(self, value):
        return value.model_copy(update={"report_token": self.issue("analysis", analysis_data(value))})

    def sign_match(self, value, text, job):
        data = {"resume_text": text, "job_description": job, "match": match_data(value)}
        return value.model_copy(update={"report_token": self.issue("match", data)})

    def verify_analysis(self, value):
        self.verify(value.report_token, "analysis", analysis_data(value))

    def verify_match(self, value, text, job):
        self.verify(value.report_token, "match", {"resume_text": text, "job_description": job, "match": match_data(value)})
