from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import os
import datetime
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("DATABASE_URL must be set in the environment")

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,   # Detect stale connections before use (fixes SSL closed unexpectedly)
    pool_recycle=300,     # Recycle connections every 5 minutes to prevent server-side timeout
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    google_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    scans = relationship("ScanHistory", back_populates="user")

class ScanHistory(Base):
    __tablename__ = "scan_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True) # Optional for now, but tied if logged in
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Input scores
    text_score = Column(Float, nullable=False)
    video_score = Column(Float, nullable=False)
    audio_score = Column(Float, nullable=False)
    is_authenticated_sender = Column(Integer, nullable=False)
    domain = Column(String, nullable=True)
    
    # Context
    raw_context_text = Column(String, nullable=True)
    
    # Results
    final_score = Column(Float, nullable=False)
    classification = Column(String, nullable=False)
    llm_threat_report = Column(String, nullable=True)
    
    user = relationship("User", back_populates="scans")
