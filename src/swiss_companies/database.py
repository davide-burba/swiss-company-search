from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class DelayedDB:
    def __init__(self):
        self._engine = None

    def setup(self, database_url: str):
        self._engine = create_engine(database_url)

    @property
    def engine(self):
        if self._engine is None:
            raise RuntimeError("Database engine not initialized. Call setup() first.")
        return self._engine


db = DelayedDB()


def get_session() -> Generator[Session, None, None]:
    with Session(db.engine) as session:
        yield session
