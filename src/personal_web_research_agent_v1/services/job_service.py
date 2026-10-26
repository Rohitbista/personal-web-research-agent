"""
services/job_service.py
────────────────────────
Manages the two parallel representations of a research job.
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from personal_web_research_agent_v1.app.models import ResearchJob
from personal_web_research_agent_v1.database.models import ResearchJobRecord, SessionRecord
from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()

_CTX = "src/services/job_service"

_live_jobs: dict[str, ResearchJob] = {}


def create_job(
    db: DBSession,
    *,
    query: str,
    session_id: str,
    trace_id: Optional[str] = None,
) -> ResearchJob:
    job_id = f"research-job-{str(uuid.uuid4())}"

    logger.info(
        "Creating research job",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id, "session_id": session_id, "query": query},
    )

    record = ResearchJobRecord(
        id=job_id,
        session_id=session_id,
        query=query,
        status="queued",
    )
    db.add(record)
    db.commit()

    live = ResearchJob(id=job_id, query=query, session_id=session_id)
    _live_jobs[job_id] = live

    logger.info(
        "Research job created and registered",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id, "status": "queued"},
    )
    return live


def get_live_job(
    job_id: str,
    trace_id: Optional[str] = None,
) -> Optional[ResearchJob]:
    logger.info(
        "Fetching live job handle",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id},
    )
    job = _live_jobs.get(job_id)
    logger.info(
        "Live job handle fetch result",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id, "found": job is not None},
    )
    return job


def get_job_record(
    db: DBSession,
    job_id: str,
    trace_id: Optional[str] = None,
) -> Optional[ResearchJobRecord]:
    logger.info(
        "Fetching job record",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id},
    )
    record = db.get(ResearchJobRecord, job_id)
    logger.info(
        "Job record fetch result",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id, "found": record is not None},
    )
    return record


def update_job_status(
    db: DBSession,
    job_id: str,
    *,
    status: str,
    report: Optional[str] = None,
    error: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    logger.info(
        "Updating job status",
        trace_id=trace_id,
        context=_CTX,
        data={
            "job_id": job_id,
            "status": status,
            "has_report": report is not None,
            "has_error": error is not None,
        },
    )
    record = db.get(ResearchJobRecord, job_id)
    if not record:
        logger.info(
            "Update skipped — job record not found",
            trace_id=trace_id,
            context=_CTX,
            data={"job_id": job_id},
        )
        return
    record.status = status
    if report is not None:
        record.report = report
    if error is not None:
        record.error = error
    db.commit()
    logger.info(
        "Job status updated",
        trace_id=trace_id,
        context=_CTX,
        data={"job_id": job_id, "status": status},
    )


def get_jobs_for_session(
    db: DBSession,
    session_id: str,
    trace_id: Optional[str] = None,
) -> list[ResearchJobRecord]:
    """Return all job rows for a session, in creation order."""
    logger.info(
        "Fetching jobs for session",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id},
    )
    records = (
        db.query(ResearchJobRecord)
        .filter(ResearchJobRecord.session_id == session_id)
        .order_by(ResearchJobRecord.created_at)
        .all()
    )
    logger.info(
        "Jobs for session fetched",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id, "count": len(records)},
    )
    return records