from sqlalchemy import Column, String, Float, Integer, DateTime
import datetime
import uuid
from layer3.db import Base

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
