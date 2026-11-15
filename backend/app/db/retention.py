"""Bounded periodic cleanup; fail closed on reads even when cleanup is unavailable."""
import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.db.repository import AnalysisRepository

logger = logging.getLogger(__name__)


async def retention_worker(repository: AnalysisRepository, stop: asyncio.Event, interval: int):
    while not stop.is_set():
        try:
            await run_in_threadpool(repository.purge_expired)
        except SQLAlchemyError:
            logger.warning("Retention cleanup unavailable; database access will not serve expired records.")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
