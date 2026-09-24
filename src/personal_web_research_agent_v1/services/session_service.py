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


def create_session(
    db: Session,
    *,
    title: str,
    session_id: Optional[str] = None,
) -> SessionRecord:
    """
    Insert a new session row.

    If ``session_id`` is supplied the caller wants a specific id
    (e.g. replaying a known id after a restart); otherwise a fresh UUID is used.
    """
    if not session_id:
        session_id = f"session-{str(uuid.uuid4())}"
    record = SessionRecord(
        id=session_id,
        title=title,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_session(db: Session, session_id: str) -> Optional[SessionRecord]:
    return db.get(SessionRecord, session_id)


def list_sessions(db: Session) -> list[SessionRecord]:
    """Return all sessions, newest first."""
    return (
        db.query(SessionRecord)
        .order_by(SessionRecord.created_at.desc())
        .all()
    )


def rename_session(
    db: Session, session_id: str, new_title: str
) -> Optional[SessionRecord]:
    """
    Update a session's title.  Returns the updated record, or None if not found.
    """
    record = db.get(SessionRecord, session_id)
    if not record:
        return None
    record.title = new_title
    db.commit()
    db.refresh(record)
    return record