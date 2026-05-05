from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from RAG import config_data as config


engine = create_engine(config.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Import models before creating tables so SQLAlchemy registers metadata.
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
