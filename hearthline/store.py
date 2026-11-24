import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


SCHEMA = Path(__file__).with_name('schema.sql')


class Store:
    def __init__(self, file):
        self.file = file
        file.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(file, timeout=5)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA.read_text(encoding='utf-8'))

    @contextmanager
    def connection(self, *, write=False):
        db = sqlite3.connect(self.file, isolation_level=None, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
