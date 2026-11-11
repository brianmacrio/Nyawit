from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_URL

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - konfigurasi koneksi
    if DB_URL.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (registrasi tabel)

    Base.metadata.create_all(engine)
    migrate_add_columns()


def migrate_add_columns() -> list[str]:
    """Migrasi aditif sederhana: kolom baru di model ditambahkan ke tabel lama (SQLite ALTER TABLE ADD COLUMN).

    Data lama tidak disentuh, jadi database dari versi sebelumnya tetap bisa dibuka.
    """
    if not DB_URL.startswith("sqlite"):
        return []
    from sqlalchemy import inspect, text

    added: list[str] = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(dialect=engine.dialect)}'
                default = getattr(col.default, "arg", None)
                if isinstance(default, bool):
                    ddl += f" DEFAULT {int(default)}"
                elif isinstance(default, (int, float)):
                    ddl += f" DEFAULT {default}"
                elif isinstance(default, str):
                    ddl += " DEFAULT '" + default.replace("'", "''") + "'"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    return added
