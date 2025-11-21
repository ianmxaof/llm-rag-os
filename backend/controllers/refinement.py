"""
Refinement Controller
---------------------
API endpoints for manual refinement triggers and refinement status.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from backend.models import RefinedDocument, SourceItem, get_db
from backend.services.refinement import RefinementService

router = APIRouter(prefix="/refinement", tags=["Refinement"])


class RefinementResponse(BaseModel):
    id: int
    title: str
    summary: str
    permanence: int
    entities: Optional[str]
    tags: List[str]
    source_url: str
    source: str
    confidence: str
    refined_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[RefinementResponse])
def list_refined_documents(
    min_permanence: int = Query(8, ge=1, le=10, description="Minimum permanence score"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List refined documents."""
    refined = (
        db.query(RefinedDocument)
        .filter(RefinedDocument.permanence >= min_permanence)
        .order_by(RefinedDocument.refined_at.desc())
        .limit(limit)
        .all()
    )
    return refined


@router.post("/refine/{source_item_id}")
def refine_item(source_item_id: int, db: Session = Depends(get_db)):
    """Manually trigger refinement for a source item."""
    source_item = db.query(SourceItem).filter(SourceItem.id == source_item_id).first()
    if not source_item:
        raise HTTPException(status_code=404, detail="Source item not found")
    
    # Check if already refined
    existing = db.query(RefinedDocument).filter(
        RefinedDocument.source_item_id == source_item_id
    ).first()
    if existing:
        return {"message": "Item already refined", "refined_document": existing}
    
    # Refine item
    refinement_service = RefinementService()
    item_dict = {
        "title": source_item.title,
        "content": source_item.content or "",
        "url": source_item.url,
        "source": source_item.source.name if source_item.source else "unknown",
        "published_at": source_item.published_at,
    }
    
    refined = refinement_service.refine_item(item_dict)
    
    if not refined:
        return {"message": "Item was SKIPped by curator", "action": "SKIP"}
    
    # Save refined document
    refined_doc = RefinedDocument(
        source_item_id=source_item_id,
        title=refined["title"],
        summary=refined["summary"],
        permanence=refined["permanence"],
        entities=refined.get("entities", ""),
        tags=refined.get("tags", []),
        source_url=refined["source_url"],
        source=refined["source"],
        content=refined.get("content", ""),
        confidence=refined.get("confidence", "medium"),
    )
    
    db.add(refined_doc)
    source_item.refined = True
    db.commit()
    db.refresh(refined_doc)
    
    return {"message": "Item refined successfully", "refined_document": refined_doc}


@router.get("/stats")
def get_refinement_stats(db: Session = Depends(get_db)):
    """Get refinement statistics."""
    total = db.query(RefinedDocument).count()
    high_permanence = db.query(RefinedDocument).filter(
        RefinedDocument.permanence >= 8
    ).count()
    ingested = db.query(RefinedDocument).filter(
        RefinedDocument.ingested == True
    ).count()
    
    return {
        "total_refined": total,
        "high_permanence": high_permanence,
        "ingested": ingested,
        "pending_ingestion": total - ingested,
    }

