from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app import db, models  # noqa: F401


def test_migrations_create_schema_matching_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.sqlite'}")
    db.set_engine(engine)
    db.migrate()
    tables = set(inspect(engine).get_table_names())
    assert {"listing", "vehicle", "saved_search", "alert", "watchlist", "alembic_version"} <= tables
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), db.Base.metadata)
    assert diff == [], diff
    db.migrate()  # idempotent


def test_existing_create_all_database_is_stamped(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 's.sqlite'}")
    db.set_engine(engine)
    db.init_db()
    db.migrate()
    assert "alembic_version" in inspect(engine).get_table_names()
