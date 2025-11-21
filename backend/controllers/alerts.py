"""
Alerts Controller
-----------------
API endpoints for secret scan alerts.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from backend.models import SecretScan, get_db

router = APIRouter(prefix="/alerts", tags=["Alerts"])


class SecretScanResponse(BaseModel):
    id: int
    source_url: str
    secrets_found: List[dict]
    scanned_at: datetime
    alerted: bool
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[SecretScanResponse])
def list_alerts(
    alerted_only: bool = Query(False, description="Only return alerted scans"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List secret scan alerts."""
    query = db.query(SecretScan)
    if alerted_only:
        query = query.filter(SecretScan.alerted == True)
    
    scans = query.order_by(SecretScan.scanned_at.desc()).limit(limit).all()
    return scans


@router.get("/{scan_id}", response_model=SecretScanResponse)
def get_alert(scan_id: int, db: Session = Depends(get_db)):
    """Get a specific secret scan."""
    scan = db.query(SecretScan).filter(SecretScan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Secret scan not found")
    return scan


@router.get("/stats")
def get_alert_stats(db: Session = Depends(get_db)):
    """Get alert statistics."""
    total = db.query(SecretScan).count()
    with_secrets = db.query(SecretScan).filter(
        SecretScan.secrets_found != []
    ).count()
    alerted = db.query(SecretScan).filter(
        SecretScan.alerted == True
    ).count()
    
    return {
        "total_scans": total,
        "secrets_found": with_secrets,
        "alerted": alerted,
    }

