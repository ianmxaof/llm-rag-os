"""
SQLAlchemy Models for Metadata Database
---------------------------------------
Defines database schema for document tracking, chunks, ingest runs, and prompts.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Float, JSON, DateTime, ForeignKey, Boolean
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine

from scripts.config import config

Base = declarative_base()

# Database path
DB_PATH = config.ROOT / "db.sqlite"
DB_URL = f"sqlite:///{DB_PATH}"

# Create engine and session factory
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Document(Base):
    """Document metadata table."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    source_path = Column(String, unique=True, index=True, nullable=False)
    file_hash = Column(String, index=True)  # MD5 hash for deduplication
    ingest_ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    ingest_version = Column(Integer, default=1, nullable=False)  # For version tracking
    status = Column(String, default="indexed", nullable=False)  # indexed, processing, error
    tags = Column(JSON, default=list)  # List of tags
    notes = Column(Text, default="")  # User notes
    
    # Relationships
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    ingest_runs = relationship("IngestRun", back_populates="document")


class Chunk(Base):
    """Chunk metadata table."""
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Index within document
    text = Column(Text)  # Optional: store chunk text (can be large)
    length = Column(Integer)  # Character length
    embedding_id = Column(String)  # Reference to ChromaDB embedding ID
    quality_score = Column(Float)  # Optional quality metric
    
    # Relationships
    document = relationship("Document", back_populates="chunks")


class IngestRun(Base):
    """Ingestion run tracking table."""
    __tablename__ = "ingest_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    start_ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_ts = Column(DateTime, nullable=True)
    files_processed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    failures_json = Column(JSON, default=dict)  # Store failure details
    status = Column(String, default="running")  # running, completed, failed
    
    # Relationships
    document = relationship("Document", back_populates="ingest_runs")


class Prompt(Base):
    """Prompt repository table."""
    __tablename__ = "prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_text = Column(Text, nullable=False)
    tags = Column(JSON, default=list)  # List of tags
    usage_count = Column(Integer, default=0, nullable=False)
    performance_score = Column(Float, default=0.0)  # Optional performance metric
    last_used = Column(DateTime, nullable=True)
    notes = Column(Text, default="")


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print(f"[INFO] Database initialized at {DB_PATH}")


def get_db():
    """Get database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
    print("[INFO] Database tables created successfully")

