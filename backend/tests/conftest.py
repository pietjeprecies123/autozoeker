import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="autozoeker-test-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_TMP / 'test.sqlite'}",
    "DATA_DIR": str(_TMP / "data"),
    "ONLINE_ENRICHMENT": "false",
    "SCHEDULER_ENABLED": "false",
    "DEMO_MODE": "true",
    "SOURCES": "demo",
    "NTFY_TOPIC": "",
    "ANTHROPIC_API_KEY": "",
    "HOME_POSTCODE": "3511",
})

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from sqlalchemy import create_engine  # noqa: E402

from app import db  # noqa: E402


@pytest.fixture()
def session():
    """Fresh in-memory database per test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    db.set_engine(engine)
    db.init_db()
    s = db.SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture(scope="session")
def seeded_engine():
    """A database with a small demo dataset and a trained valuation model (shared, read-mostly)."""
    from app.analysis import refresh
    from app.demo.seed import seed_demo

    path = _TMP / "seeded.sqlite"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    db.set_engine(engine)
    db.init_db()
    with db.session_scope() as s:
        seed_demo(s, n=1200, seed=7)
    with db.session_scope() as s:
        refresh(s, retrain=True)
    return engine


@pytest.fixture()
def seeded(seeded_engine):
    db.set_engine(seeded_engine)
    s = db.SessionLocal()
    try:
        yield s
        s.rollback()
    finally:
        s.close()
