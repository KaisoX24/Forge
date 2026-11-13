from contextlib import contextmanager
from collections.abc import Generator

from sqlalchemy import Engine,create_engine,event
from sqlalchemy.orm import Session,sessionmaker

from api.storage.models import Base

def make_engine(url:str="sqlite:///data/learner.db") ->Engine:
    engine=create_engine(url)
    if engine.dialect.name=='sqlite':
        @event.listens_for(engine,'connect')
        def _sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine

def init_db(engine:Engine)->None:
    Base.metadata.create_all(engine)

def make_session_factory(engine:Engine) ->sessionmaker[Session]:
    return sessionmaker(engine,expire_on_commit=False)

@contextmanager
def session_scope(factory:sessionmaker[Session]) -> Generator[Session,None,None]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()