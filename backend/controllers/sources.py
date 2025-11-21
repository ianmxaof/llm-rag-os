"""
Sources Controller
------------------
API endpoints for managing data sources.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.models import Source, get_db
from backend.collectors import GitHubCollector, RSSCollector, ArxivCollector, RedditCollector

router = APIRouter(prefix="/sources", tags=["Sources"])


class SourceCreate(BaseModel):
    source_type: str
    name: str
    config: dict
    enabled: bool = True


class SourceResponse(BaseModel):
    id: int
    source_type: str
    name: str
    config: dict
    enabled: bool
    last_collected: Optional[datetime]
    items_collected: int
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[SourceResponse])
def list_sources(
    enabled_only: bool = Query(False, description="Only return enabled sources"),
    db: Session = Depends(get_db)
):
    """List all data sources."""
    query = db.query(Source)
    if enabled_only:
        query = query.filter(Source.enabled == True)
    sources = query.all()
    return sources


@router.post("/", response_model=SourceResponse)
def create_source(source: SourceCreate, db: Session = Depends(get_db)):
    """Create a new data source."""
    db_source = Source(
        source_type=source.source_type,
        name=source.name,
        config=source.config,
        enabled=source.enabled,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)):
    """Get a specific source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.put("/{source_id}", response_model=SourceResponse)
def update_source(
    source_id: int,
    source: SourceCreate,
    db: Session = Depends(get_db)
):
    """Update a source."""
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db_source.source_type = source.source_type
    db_source.name = source.name
    db_source.config = source.config
    db_source.enabled = source.enabled
    
    db.commit()
    db.refresh(db_source)
    return db_source


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(source)
    db.commit()
    return {"message": "Source deleted"}


@router.post("/{source_id}/collect")
def collect_from_source(source_id: int, db: Session = Depends(get_db)):
    """Manually trigger collection from a source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if not source.enabled:
        raise HTTPException(status_code=400, detail="Source is disabled")
    
    # Get collector based on source type
    collector = None
    if source.source_type == "github":
        collector = GitHubCollector(source.config)
    elif source.source_type == "rss":
        collector = RSSCollector(source.config)
    elif source.source_type == "arxiv":
        collector = ArxivCollector(source.config)
    elif source.source_type == "reddit":
        collector = RedditCollector(source.config)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown source type: {source.source_type}")
    
    # Collect items
    items = collector.collect(since=source.last_collected)
    
    # Update source
    source.last_collected = datetime.utcnow()
    source.items_collected += len(items)
    db.commit()
    
    return {
        "message": f"Collected {len(items)} items",
        "items": items[:10],  # Return first 10 as preview
    }

