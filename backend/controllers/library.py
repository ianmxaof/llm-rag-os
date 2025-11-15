"""
Library Controller
------------------
Manages document library: list, get, update metadata, delete.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from backend.models import Document, Chunk, SessionLocal
from scripts.config import config
import chromadb

logger = logging.getLogger(__name__)
router = APIRouter()


def list_documents(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    tag: Optional[str] = None
) -> Dict:
    """List documents with pagination and filters."""
    db = SessionLocal()
    try:
        query = db.query(Document)
        
        if status:
            query = query.filter(Document.status == status)
        if tag:
            query = query.filter(Document.tags.contains([tag]))
        
        total = query.count()
        docs = query.order_by(Document.ingest_ts.desc()).offset(offset).limit(limit).all()
        
        items = []
        for doc in docs:
            items.append({
                "id": doc.id,
                "source_path": doc.source_path,
                "file_hash": doc.file_hash,
                "ingest_ts": doc.ingest_ts.isoformat() if doc.ingest_ts else None,
                "ingest_version": doc.ingest_version,
                "status": doc.status,
                "tags": doc.tags or [],
                "notes": doc.notes
            })
        
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    finally:
        db.close()


def get_document(doc_id: int) -> Dict:
    """Get document details including sample chunks."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get chunks for this document
        chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.chunk_index).limit(5).all()
        
        # Try to get chunks from ChromaDB
        chroma_chunks = []
        try:
            client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
            collection = client.get_collection(config.COLLECTION_NAME)
            # Query by source path metadata
            results = collection.get(
                where={"source": doc.source_path},
                limit=5
            )
            chroma_chunks = results.get("documents", [])
        except Exception as e:
            logger.warning(f"Could not fetch ChromaDB chunks: {e}")
        
        return {
            "id": doc.id,
            "source_path": doc.source_path,
            "file_hash": doc.file_hash,
            "ingest_ts": doc.ingest_ts.isoformat() if doc.ingest_ts else None,
            "ingest_version": doc.ingest_version,
            "status": doc.status,
            "tags": doc.tags or [],
            "notes": doc.notes,
            "chunks": [
                {
                    "chunk_index": c.chunk_index,
                    "text": c.text[:500] + "..." if c.text and len(c.text) > 500 else c.text,
                    "length": c.length
                }
                for c in chunks
            ],
            "chroma_chunks_preview": chroma_chunks[:3]  # First 3 chunks from ChromaDB
        }
    finally:
        db.close()


def update_document_metadata(doc_id: int, tags: Optional[List[str]] = None, notes: Optional[str] = None) -> Dict:
    """Update document metadata."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if tags is not None:
            doc.tags = tags
        if notes is not None:
            doc.notes = notes
        
        db.commit()
        return {
            "success": True,
            "message": "Metadata updated successfully",
            "document": {
                "id": doc.id,
                "tags": doc.tags,
                "notes": doc.notes
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def delete_document(doc_id: int) -> Dict:
    """Delete document from both SQLite and ChromaDB."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        source_path = doc.source_path
        
        # Delete from ChromaDB
        try:
            client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
            collection = client.get_collection(config.COLLECTION_NAME)
            # Get all IDs for this source
            results = collection.get(where={"source": source_path})
            ids_to_delete = results.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} chunks from ChromaDB")
        except Exception as e:
            logger.warning(f"Could not delete from ChromaDB: {e}")
        
        # Delete from SQLite (cascade will delete chunks)
        db.delete(doc)
        db.commit()
        
        return {
            "success": True,
            "message": f"Document {doc_id} deleted successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/list")
def list_documents_endpoint(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    tag: Optional[str] = None
):
    """List documents with pagination."""
    return list_documents(limit=limit, offset=offset, status=status, tag=tag)


@router.get("/document/{doc_id}")
def get_document_endpoint(doc_id: int):
    """Get document details."""
    return get_document(doc_id)


@router.post("/document/{doc_id}/metadata")
def update_metadata_endpoint(
    doc_id: int,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None
):
    """Update document metadata."""
    return update_document_metadata(doc_id, tags=tags, notes=notes)


@router.delete("/document/{doc_id}")
def delete_document_endpoint(doc_id: int):
    """Delete document."""
    return delete_document(doc_id)

