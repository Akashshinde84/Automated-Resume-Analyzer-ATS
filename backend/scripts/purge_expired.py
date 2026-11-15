"""Run from an external scheduler as well as the app's in-process cleanup worker."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.db.repository import AnalysisRepository
from app.db.session import Database


def main():
    database = None
    try:
        settings = Settings()
        if not settings.storage_enabled:
            print('Storage disabled; no cleanup needed.')
            return 0
        database = Database(settings.database_url.get_secret_value())
        count = AnalysisRepository(database, settings).purge_expired()
        print(f'Expired analyses purged: {count}')
        return 0
    except Exception:
        print('Cleanup failed; verify configuration and database availability.', file=sys.stderr)
        return 1
    finally:
        if database:
            database.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
