"""Engines are app-scoped; sessions/transactions are operation-scoped."""
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def normalize_database_url(value):
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    url = make_url(value)
    if url.drivername not in {"postgresql+psycopg", "sqlite", "sqlite+pysqlite"}:
        raise ValueError("Use PostgreSQL with psycopg or SQLite for isolated local tests.")
    return url


class Database:
    def __init__(self, url):
        url = normalize_database_url(url)
        options = dict(pool_pre_ping=True, echo=False, hide_parameters=True)
        if url.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False, "timeout": 5}
            if url.database in {None, "", ":memory:"}:
                options["poolclass"] = StaticPool
        else:
            options["connect_args"] = {"connect_timeout": 5, "options": (str(url.query.get("options", "")) + " -c statement_timeout=5000").strip()}
        self.engine = create_engine(url, **options)
        if url.get_backend_name() == "sqlite":
            @event.listens_for(self.engine, "connect")
            def sqlite_foreign_keys(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self):
        self.engine.dispose()
