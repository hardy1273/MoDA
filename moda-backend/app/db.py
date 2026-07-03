from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

BASELINE_REVISION = "0001"

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_config():
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


def init_db() -> None:
    """Bring the schema to the latest Alembic revision.

    Databases created before Alembic (via create_all) are adopted by
    stamping the baseline revision first, then upgrading normally.
    """
    from alembic import command

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    cfg = _alembic_config()
    inspector = inspect(engine)
    if inspector.has_table("users") and not inspector.has_table("alembic_version"):
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
