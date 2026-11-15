"""Private single-owner history; bounded transactions and retention on every access."""
from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

from sqlalchemy import delete, func, or_, select

from app.db.models import Analysis, JobDescription, MatchResult, StructuredResume
from app.schemas.analysis import AnalysisDetail, AnalysisPage, AnalysisResponse, AnalysisSummary, StoredMatch


class HistoryNotFound(Exception):
    pass


class HistoryLimitExceeded(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AnalysisRepository:
    def __init__(self, database, settings):
        self.database, self.settings = database, settings
        self.owner = settings.single_user_id

    def _purge(self, session):
        now = utcnow()
        cutoff = now - timedelta(days=self.settings.retention_days)
        return session.execute(delete(Analysis).where(or_(Analysis.expires_at <= now, Analysis.created_at <= cutoff))).rowcount

    def purge_expired(self):
        with self.database.sessions.begin() as session:
            return self._purge(session)

    def _analysis(self, session, analysis_id, lock=False):
        query = select(Analysis).where(Analysis.id == analysis_id, Analysis.owner_id == self.owner)
        if lock:
            query = query.with_for_update()
        row = session.scalar(query)
        if row is None:
            raise HistoryNotFound()
        now = utcnow()
        if self._expiry(row) <= now:
            raise HistoryNotFound()
        return row

    def _expiry(self, row):
        return min(aware(row.expires_at), aware(row.created_at) + timedelta(days=self.settings.retention_days))

    def save(self, result: AnalysisResponse):
        now, ident = utcnow(), uuid4()
        expiry = now + timedelta(days=self.settings.retention_days)
        with self.database.sessions.begin() as session:
            self._purge(session)
            if session.bind.dialect.name == "postgresql":
                # Serialize this owner's quota checks across processes/replicas.
                lock = int.from_bytes(hashlib.sha256(self.owner.encode()).digest()[:8], "big", signed=True)
                session.execute(select(func.pg_advisory_xact_lock(lock)))
            count = session.scalar(select(func.count()).select_from(Analysis).where(Analysis.owner_id == self.owner))
            if count >= self.settings.max_stored_analyses:
                raise HistoryLimitExceeded()
            session.add(Analysis(id=ident, owner_id=self.owner, created_at=now, expires_at=expiry, file_type=result.parsed.metadata.file_type))
            session.flush()
            session.add(StructuredResume(analysis_id=ident, parsed=result.parsed.model_dump(mode="json"), extraction=result.extraction.model_dump(mode="json")))
        return result.model_copy(update={"id": ident, "stored": True, "created_at": now, "expires_at": expiry})

    def get(self, ident, match_limit=20, match_offset=0):
        with self.database.sessions.begin() as session:
            self._purge(session)
            row = self._analysis(session, ident)
            data = session.get(StructuredResume, row.id)
            if data is None:
                raise HistoryNotFound()
            matches = session.execute(select(MatchResult, JobDescription.text).join(JobDescription, MatchResult.job_description_id == JobDescription.id)
                                      .where(MatchResult.analysis_id == row.id).order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
                                      .limit(match_limit).offset(match_offset)).all()
            total = session.scalar(select(func.count()).select_from(MatchResult).where(MatchResult.analysis_id == row.id))
            return AnalysisDetail(id=row.id, stored=True, created_at=aware(row.created_at), expires_at=self._expiry(row),
                parsed=data.parsed, extraction=data.extraction, match_count=total, matches_limit=match_limit, matches_offset=match_offset,
                matches=[StoredMatch(id=m.id, created_at=aware(m.created_at), job_description=text, result=m.result) for m, text in matches])

    def resume_for_match(self, ident):
        with self.database.sessions.begin() as session:
            self._purge(session)
            row = self._analysis(session, ident)
            data = session.get(StructuredResume, row.id)
            if data is None:
                raise HistoryNotFound()
            return {"text": data.parsed["text"]}

    def get_match(self, analysis_id, match_id):
        """Fetch exactly one match under a live, owned parent, never by match ID alone."""
        with self.database.sessions.begin() as session:
            self._purge(session)
            self._analysis(session, analysis_id)
            row = session.execute(select(MatchResult, JobDescription.text)
                .join(JobDescription, MatchResult.job_description_id == JobDescription.id)
                .where(MatchResult.id == match_id, MatchResult.analysis_id == analysis_id,
                       JobDescription.analysis_id == analysis_id)).first()
            if row is None:
                raise HistoryNotFound()
            match, text = row
            return StoredMatch(id=match.id, created_at=aware(match.created_at), job_description=text, result=match.result)

    def list(self, limit, offset):
        with self.database.sessions.begin() as session:
            self._purge(session)
            query = select(Analysis).where(Analysis.owner_id == self.owner)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rows = session.scalars(query.order_by(Analysis.created_at.desc(), Analysis.id.desc()).limit(limit).offset(offset)).all()
            return AnalysisPage(items=[AnalysisSummary(id=row.id, created_at=aware(row.created_at), expires_at=self._expiry(row), file_type=row.file_type) for row in rows],
                                total=total, limit=limit, offset=offset)

    def delete(self, ident):
        with self.database.sessions.begin() as session:
            self._purge(session)
            row = self._analysis(session, ident, lock=True)
            session.delete(row)

    def save_match(self, analysis_id, job_text, result):
        ident, job_id, now = uuid4(), uuid4(), utcnow()
        with self.database.sessions.begin() as session:
            self._purge(session)
            self._analysis(session, analysis_id, lock=True)
            count = session.scalar(select(func.count()).select_from(MatchResult).where(MatchResult.analysis_id == analysis_id))
            if count >= self.settings.max_matches_per_analysis:
                raise HistoryLimitExceeded()
            session.add(JobDescription(id=job_id, analysis_id=analysis_id, created_at=now, text=job_text))
            session.flush()
            session.add(MatchResult(id=ident, analysis_id=analysis_id, job_description_id=job_id, created_at=now, result=result.model_dump(mode="json")))
        return ident
