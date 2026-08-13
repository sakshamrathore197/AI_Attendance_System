from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
DATABASE_URL = "sqlite:///attendance.db"
print("Current Working Directory:", os.getcwd())
print("Absolute DB Path:", os.path.abspath("attendance.db"))
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()