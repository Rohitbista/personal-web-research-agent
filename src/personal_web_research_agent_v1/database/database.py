"""
database/database.py
─────────────────────
Engine setup, session factory, lifespan helper, and FastAPI dependency.

The SQLite file lives at  database/research.db  (added to .gitignore).
To swap to Postgres later, replace DB_URL with a postgresql+asyncpg:// URL
and change create_engine → create_async_engine throughout.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

# ── Path resolution ───────────────────────────────────────────────────────────

# Resolves to  <project_root>/src/.../database/research.db
# regardless of where the process is launched from.
_DB_DIR = Path(__file__).parent
DB_PATH = _DB_DIR / "research.db"
DB_URL = f"sqlite:///{DB_PATH}"

# ── Engine ────────────────────────────────────────────────────────────────────

# check_same_thread=False is required for SQLite when FastAPI runs handlers
# on a thread pool (which it does for sync dependencies and to_thread calls).
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,   # set True to log every SQL statement while debugging
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ── Schema init ───────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they don't exist yet. Call once at startup."""
    Base.metadata.create_all(bind=engine)


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_db():
    """
    Yields a SQLAlchemy Session and guarantees it is closed afterwards.

    Usage in a route or service:
        def my_endpoint(db: Session = Depends(get_db)): ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()