from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Create data directory if it doesn't exist
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_URL = f"sqlite:///{os.path.join(DATA_DIR, 'layer3.db')}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import Column, String, Float, Integer, DateTime
import datetime
import uuid

class ScanHistory(Base):
    __tablename__ = "scan_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
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
