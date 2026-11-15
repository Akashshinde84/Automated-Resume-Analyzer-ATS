"""No credentials in ini files or migration log output."""
from alembic import context
from sqlalchemy import create_engine

from app.core.config import Settings
from app.db.models import Base
from app.db.session import Database, normalize_database_url

config = context.config
target_metadata = Base.metadata


def run():
    url = config.attributes.get("database_url")
    if not url:
        secret = Settings().database_url
        if not secret or not secret.get_secret_value():
            raise RuntimeError("DATABASE_URL is required for migrations.")
        url = secret.get_secret_value()
    if context.is_offline_mode():
        context.configure(url=normalize_database_url(url), target_metadata=target_metadata,
                          literal_binds=True, dialect_opts={"paramstyle": "named"})
        with context.begin_transaction():
            context.run_migrations()
    else:
        database = Database(url)
        try:
            with database.engine.connect() as connection:
                context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            database.dispose()


run()
