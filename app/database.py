from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Email(Base):
    __tablename__ = "emails"
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True)
    email_id = Column(String, unique=True, index=True)
    subject = Column(String)
    body = Column(String)
    is_read = Column(Boolean, default=False)
    reading_duration = Column(Float, default=0.0)  # seconds
    is_urgent = Column(Boolean, default=None)      # None = not classified yet
    created_at = Column(DateTime, server_default=func.now())

def init_db():
    Base.metadata.create_all(bind=engine)
