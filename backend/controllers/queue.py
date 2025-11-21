"""
Queue Controller
----------------
API endpoints for managing the ingestion queue.
"""

from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.services.ingestion_queue import IngestionQueue

router = APIRouter(prefix="/queue", tags=["Queue"])


class QueueStatsResponse(BaseModel):
    processed: int
    pending: int
    queue_dir: str


@router.get("/stats", response_model=QueueStatsResponse)
def get_queue_stats():
    """Get queue statistics."""
    queue = IngestionQueue()
    return queue.get_stats()


@router.get("/pending")
def get_pending_items(limit: int = 10):
    """Get pending items from queue."""
    queue = IngestionQueue()
    items = queue.get_pending_items(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/clear")
def clear_pending():
    """Clear the pending queue."""
    queue = IngestionQueue()
    queue.clear_pending()
    return {"message": "Pending queue cleared"}

