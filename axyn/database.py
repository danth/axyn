from contextlib import contextmanager
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from typing import Optional


def get_path(file):
    """Return the path of the given file within Axyn's data directory."""

    # Find path of data directory
    folder = os.path.expanduser("~/axyn")
    # Create directory if it doesn't exist
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, file)


class BaseRecord(DeclarativeBase):
    """Base class for database records."""


class ConsentRecord(BaseRecord):
    """Database record storing whether a user has consented to data collection."""

    __tablename__ = "consent"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    consented: Mapped[Optional[bool]]


class ResponseRecord(BaseRecord):
    """Database record storing a learned response."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    ngt_id: Mapped[int]
    response: Mapped[str]
    meta: Mapped[str]


class DatabaseManager:
    """Holds a connection to the database and constructs database sessions."""

    def __init__(self):
        uri = "sqlite:///" + get_path("database.sqlite3")
        engine = create_engine(uri)
        BaseRecord.metadata.create_all(engine)
        self._session_maker = sessionmaker(bind=engine)

    @contextmanager
    def session(self):
        session = self._session_maker()
        session.begin()

        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()


