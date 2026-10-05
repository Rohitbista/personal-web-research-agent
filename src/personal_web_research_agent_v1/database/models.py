"""
database/models.py
──────────────────
SQLAlchemy ORM table definitions.

These are the *persisted* shapes of Session and ResearchJob.
The runtime dataclasses in app/models.py (with asyncio.Queue, threading.Event, etc.)
are kept separate because those fields can never be serialised to a DB.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from personal_web_research_agent_v1.config.nepal_time import nepal_date_now


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=nepal_date_now
    )

    # One session → many research jobs
    jobs: Mapped[list["ResearchJobRecord"]] = relationship(
        "ResearchJobRecord",
        back_populates="session",
        order_by="ResearchJobRecord.created_at",
        lazy="selectin",   # avoids N+1 when listing sessions
    )


class ResearchJobRecord(Base):
    __tablename__ = "research_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="queued"
    )  # queued | running | completed | failed | cancelled
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=nepal_date_now
    )

    session: Mapped["SessionRecord"] = relationship(
        "SessionRecord", back_populates="jobs"
    )