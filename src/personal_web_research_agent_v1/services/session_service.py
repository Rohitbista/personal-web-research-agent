"""
services/session_service.py
────────────────────────────
All session-level persistence.  Routes never touch the DB directly —
they call these functions and get back plain ORM records.
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from personal_web_research_agent_v1.database.models import SessionRecord
from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()

_CTX = "src/services/session_service"


def create_session(
    db: Session,
    *,
    title: str,
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> SessionRecord:
    """
    Insert a new session row.

    If ``session_id`` is supplied the caller wants a specific id
    (e.g. replaying a known id after a restart); otherwise a fresh UUID is used.
    """
    if not session_id:
        session_id = f"session-{str(uuid.uuid4())}"

    logger.info(
        "Creating session",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id, "title": title},
    )

    record = SessionRecord(id=session_id, title=title)
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        "Session created",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id},
    )
    return record


def get_session(
    db: Session,
    session_id: str,
    trace_id: Optional[str] = None,
) -> Optional[SessionRecord]:
    logger.info(
        "Fetching session",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id},
    )
    record = db.get(SessionRecord, session_id)
    logger.info(
        "Session fetch result",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id, "found": record is not None},
    )
    return record


def list_sessions(
    db: Session,
    trace_id: Optional[str] = None,
) -> list[SessionRecord]:
    """Return all sessions, newest first."""
    logger.info(
        "Listing all sessions",
        trace_id=trace_id,
        context=_CTX,
    )
    records = (
        db.query(SessionRecord)
        .order_by(SessionRecord.created_at.desc())
        .all()
    )
    logger.info(
        "Sessions listed",
        trace_id=trace_id,
        context=_CTX,
        data={"count": len(records)},
    )
    return records


def rename_session(
    db: Session,
    session_id: str,
    new_title: str,
    trace_id: Optional[str] = None,
) -> Optional[SessionRecord]:
    """
    Update a session's title.  Returns the updated record, or None if not found.
    """
    logger.info(
        "Renaming session",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id, "new_title": new_title},
    )
    record = db.get(SessionRecord, session_id)
    if not record:
        logger.info(
            "Rename skipped — session not found",
            trace_id=trace_id,
            context=_CTX,
            data={"session_id": session_id},
        )
        return None
    record.title = new_title
    db.commit()
    db.refresh(record)
    logger.info(
        "Session renamed",
        trace_id=trace_id,
        context=_CTX,
        data={"session_id": session_id},
    )
    return record