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


class Source(Base):
    """Data source configuration table."""
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False, index=True)  # rss, github, arxiv, reddit, etc.
    name = Column(String, nullable=False)
    config = Column(JSON, default=dict)  # Source-specific configuration
    enabled = Column(Boolean, default=True, nullable=False)
    last_collected = Column(DateTime, nullable=True)
    items_collected = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SourceItem(Base):
    """Raw items collected from sources (before refinement)."""
    __tablename__ = "source_items"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text)
    url = Column(String, nullable=False, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    raw_data = Column(JSON, default=dict)  # Original item data
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    refined = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    source = relationship("Source")


class RefinedDocument(Base):
    """Refined documents after LLM curation."""
    __tablename__ = "refined_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    source_item_id = Column(Integer, ForeignKey("source_items.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    permanence = Column(Integer, nullable=False, index=True)  # 1-10 score
    entities = Column(String)  # Comma-separated entities
    tags = Column(JSON, default=list)
    source_url = Column(String, nullable=False)
    source = Column(String, nullable=False)
    content = Column(Text)
    confidence = Column(String)  # high/medium/low
    refined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ingested = Column(Boolean, default=False, nullable=False)
    ingested_at = Column(DateTime, nullable=True)
    
    # Relationships
    source_item = relationship("SourceItem")


class SecretScan(Base):
    """Secret scan results."""
    __tablename__ = "secret_scans"
    
    id = Column(Integer, primary_key=True, index=True)
    source_item_id = Column(Integer, ForeignKey("source_items.id"), nullable=True, index=True)
    source_url = Column(String, nullable=False)
    secrets_found = Column(JSON, default=list)  # List of found secrets
    scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    alerted = Column(Boolean, default=False, nullable=False)


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

