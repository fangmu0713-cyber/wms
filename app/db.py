"""On-disk transactional store. Migrations run explicitly, never against a remote DB."""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager


def default_path():
    return os.environ.get('WMS_DB_PATH', 'var/wms.sqlite3')


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect(path):
    db = sqlite3.connect(path, timeout=15, isolation_level=None, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=15000')
    return db


def migrate(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        for script in sorted((Path(__file__).parent / 'migrations').glob('*.sql')):
            if not db.execute('SELECT 1 FROM schema_migrations WHERE version=?', (script.name,)).fetchone():
                try:
                    db.executescript('BEGIN IMMEDIATE;\n' + script.read_text() + "\nINSERT INTO schema_migrations(version) VALUES ('" + script.name + "');\nCOMMIT;")
                except BaseException:
                    if db.in_transaction:
                        db.rollback()
                    raise


@contextmanager
def transaction(path):
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
