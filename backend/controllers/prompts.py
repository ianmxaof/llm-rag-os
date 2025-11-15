"""
Prompt Repository Controller
----------------------------
Manages prompt repository: list, create, update, track usage.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Body
from sqlalchemy.orm import Session

from backend.models import Prompt, SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()


def list_prompts(limit: int = 100, offset: int = 0, tag: Optional[str] = None) -> Dict:
    """List prompts with pagination."""
    db = SessionLocal()
    try:
        query = db.query(Prompt)
        
        if tag:
            query = query.filter(Prompt.tags.contains([tag]))
        
        total = query.count()
        prompts = query.order_by(Prompt.usage_count.desc()).offset(offset).limit(limit).all()
        
        items = []
        for prompt in prompts:
            items.append({
                "id": prompt.id,
                "prompt_text": prompt.prompt_text,
                "tags": prompt.tags or [],
                "usage_count": prompt.usage_count,
                "performance_score": prompt.performance_score,
                "last_used": prompt.last_used.isoformat() if prompt.last_used else None,
                "notes": prompt.notes
            })
        
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    finally:
        db.close()


def create_prompt(prompt_text: str, tags: Optional[List[str]] = None, notes: Optional[str] = None) -> Dict:
    """Create a new prompt."""
    db = SessionLocal()
    try:
        prompt = Prompt(
            prompt_text=prompt_text,
            tags=tags or [],
            notes=notes or ""
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        
        return {
            "success": True,
            "message": "Prompt created successfully",
            "prompt": {
                "id": prompt.id,
                "prompt_text": prompt.prompt_text,
                "tags": prompt.tags,
                "notes": prompt.notes
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def update_prompt(
    prompt_id: int,
    prompt_text: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None
) -> Dict:
    """Update prompt metadata."""
    db = SessionLocal()
    try:
        prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        if prompt_text is not None:
            prompt.prompt_text = prompt_text
        if tags is not None:
            prompt.tags = tags
        if notes is not None:
            prompt.notes = notes
        
        db.commit()
        return {
            "success": True,
            "message": "Prompt updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def track_usage(prompt_id: int) -> Dict:
    """Track prompt usage (increment count, update last_used)."""
    db = SessionLocal()
    try:
        prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        prompt.usage_count += 1
        prompt.last_used = datetime.utcnow()
        
        db.commit()
        return {
            "success": True,
            "message": "Usage tracked",
            "usage_count": prompt.usage_count
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error tracking usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/list")
def list_prompts_endpoint(
    limit: int = 100,
    offset: int = 0,
    tag: Optional[str] = None
):
    """List prompts."""
    return list_prompts(limit=limit, offset=offset, tag=tag)


@router.post("/create")
def create_prompt_endpoint(
    prompt_text: str = Body(..., embed=True),
    tags: Optional[List[str]] = Body(None, embed=True),
    notes: Optional[str] = Body(None, embed=True)
):
    """Create a new prompt."""
    return create_prompt(prompt_text=prompt_text, tags=tags, notes=notes)


@router.post("/{prompt_id}/update")
def update_prompt_endpoint(
    prompt_id: int,
    prompt_text: Optional[str] = Body(None, embed=True),
    tags: Optional[List[str]] = Body(None, embed=True),
    notes: Optional[str] = Body(None, embed=True)
):
    """Update prompt."""
    return update_prompt(prompt_id, prompt_text=prompt_text, tags=tags, notes=notes)


@router.post("/{prompt_id}/track-usage")
def track_usage_endpoint(prompt_id: int):
    """Track prompt usage."""
    return track_usage(prompt_id)

