

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import get_settings

log = logging.getLogger("database")

_s = get_settings()
DATABASE_URL = _s.database_url
SQL_ECHO = _s.sql_echo

log.info(f"Connecting to database  echo={SQL_ECHO}")
log.debug("DATABASE_URL loaded (length=%s)", len(DATABASE_URL))

engine = create_engine(
    DATABASE_URL,
    echo            = SQL_ECHO,
    pool_pre_ping   = True,     # detect stale connections automatically
    pool_size       = 5,
    max_overflow    = 10,
)

SessionLocal = sessionmaker(
    bind        = engine,
    autoflush   = False,
    autocommit  = False,
)

Base = declarative_base()

log.info("Database engine ready")



def get_db():
   
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
