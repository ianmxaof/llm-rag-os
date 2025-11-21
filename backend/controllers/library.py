"""
Library Controller
------------------
Manages document library: list, get, update metadata, delete.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from backend.models import Document, Chunk, SessionLocal
from scripts.config import config
from scripts.enrichment import enrich_document
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


@router.get("/chunks")
def get_chunks_endpoint(
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """
    Get chunks directly from ChromaDB collection.
    This endpoint queries ChromaDB to show actual ingested content,
    regardless of SQLite Document records.
    """
    try:
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        
        # Check if collection exists, create if it doesn't
        try:
            collection = client.get_collection(config.COLLECTION_NAME)
        except Exception:
            # Collection doesn't exist yet
            logger.info(f"Collection {config.COLLECTION_NAME} does not exist yet")
            return {
                "chunks": [],
                "total": 0,
                "sources": 0,
                "limit": limit,
                "offset": offset,
                "error": f"Collection '{config.COLLECTION_NAME}' does not exist. Ingest some documents first."
            }
        
        # Get count first to handle empty collections
        try:
            count = collection.count()
            if count == 0:
                return {
                    "chunks": [],
                    "total": 0,
                    "sources": 0,
                    "limit": limit,
                    "offset": offset
                }
        except Exception as e:
            logger.warning(f"Could not get collection count: {e}")
        
        # Get chunks with metadata and documents
        try:
            results = collection.get(
                limit=limit + offset,
                include=["metadatas", "documents", "ids"]
            )
        except Exception as e:
            logger.error(f"Error getting chunks from collection: {e}")
            return {
                "chunks": [],
                "total": 0,
                "sources": 0,
                "limit": limit,
                "offset": offset,
                "error": f"Error querying collection: {str(e)}"
            }
        
        # Ensure we have valid results
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        
        # Check if results are empty
        if not ids or len(ids) == 0:
            return {
                "chunks": [],
                "total": 0,
                "sources": 0,
                "limit": limit,
                "offset": offset
            }
        
        # Apply offset manually (ChromaDB doesn't support offset directly)
        ids = ids[offset:offset+limit] if offset < len(ids) else []
        metadatas = metadatas[offset:offset+limit] if offset < len(metadatas) else []
        documents = documents[offset:offset+limit] if offset < len(documents) else []
        
        # Ensure all lists have the same length
        min_len = min(len(ids), len(metadatas), len(documents))
        ids = ids[:min_len]
        metadatas = metadatas[:min_len]
        documents = documents[:min_len]
        
        # Group chunks by source document
        chunks_by_source = {}
        for chunk_id, meta, doc in zip(ids, metadatas, documents):
            source = meta.get("source", "unknown")
            chunk_idx = meta.get("chunk", 0)
            file_hash = meta.get("file_hash", "")
            
            if source not in chunks_by_source:
                chunks_by_source[source] = []
            
            chunks_by_source[source].append({
                "id": chunk_id,
                "source": source,
                "chunk_index": chunk_idx,
                "file_hash": file_hash,
                "text_preview": doc[:500] + "..." if len(doc) > 500 else doc,
                "text_length": len(doc),
                "metadata": meta
            })
        
        # Convert to list format
        chunks_list = []
        for source, chunks in chunks_by_source.items():
            chunks_list.extend(chunks)
        
        return {
            "chunks": chunks_list,
            "total": len(chunks_list),
            "sources": len(chunks_by_source),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting chunks from ChromaDB: {e}")
        return {
            "chunks": [],
            "total": 0,
            "sources": 0,
            "error": str(e)
        }


@router.get("/archived")
def get_archived_documents(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get archived markdown files with AI-generated summaries and tags.
    
    Args:
        page: Page number (1-indexed)
        search: Optional search term to filter by filename
        limit: Number of files per page
        
    Returns:
        Dictionary with files list and pagination info
    """
    try:
        archive_dir = config.ARCHIVE
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Get all .md files, sorted by modification time (newest first)
        files = sorted(
            archive_dir.glob("*.md"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            files = [f for f in files if search_lower in f.name.lower()]
        
        total_files = len(files)
        
        # Pagination
        start = (page - 1) * limit
        end = start + limit
        page_files = files[start:end]
        
        results = []
        for f in page_files:
            try:
                # Read file content
                content = f.read_text(encoding="utf-8", errors="ignore")
                preview = content[:800]
                
                # Generate AI summary and tags (use cached or generate)
                # For performance, we could cache these, but for now generate on-demand
                try:
                    enrichment = enrich_document(preview)
                    ai_summary = enrichment.get("summary", "")
                    ai_tags = enrichment.get("tags", [])
                except Exception as e:
                    logger.warning(f"Could not enrich {f.name}: {e}")
                    ai_summary = preview[:200] + "..." if len(preview) > 200 else preview
                    ai_tags = []
                
                # Get file stats
                stat = f.stat()
                results.append({
                    "name": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "preview": preview,
                    "ai_summary": ai_summary,
                    "ai_tags": ai_tags
                })
            except Exception as e:
                logger.error(f"Error processing file {f.name}: {e}")
                # Still include file with minimal info
                stat = f.stat()
                results.append({
                    "name": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "preview": "",
                    "ai_summary": "",
                    "ai_tags": [],
                    "error": str(e)
                })
        
        return {
            "files": results,
            "total": total_files,
            "page": page,
            "limit": limit,
            "pages": (total_files + limit - 1) // limit if limit > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting archived documents: {e}")
        return {
            "files": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "pages": 0,
            "error": str(e)
        }


@router.get("/tags")
def get_tags():
    """
    Get all tags and their file counts from tag directories.
    
    Returns:
        Dictionary with tags list and counts
    """
    try:
        tags_dir = config.TAGS_DIR
        tags_dir.mkdir(parents=True, exist_ok=True)
        
        tags_info = []
        for tag_dir in tags_dir.iterdir():
            if tag_dir.is_dir():
                tag_name = tag_dir.name
                # Count files in tag directory
                file_count = len(list(tag_dir.glob("*.md")))
                tags_info.append({
                    "tag": tag_name,
                    "count": file_count
                })
        
        # Sort by count (descending)
        tags_info.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "tags": tags_info,
            "total": len(tags_info)
        }
        
    except Exception as e:
        logger.error(f"Error getting tags: {e}")
        return {
            "tags": [],
            "total": 0,
            "error": str(e)
        }


@router.get("/tag/{tag}")
def get_files_by_tag(
    tag: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get files for a specific tag.
    
    Args:
        tag: Tag name (normalized)
        page: Page number
        limit: Files per page
        
    Returns:
        Dictionary with files list
    """
    try:
        tags_dir = config.TAGS_DIR
        tag_normalized = tag.lower().replace(" ", "_").replace("/", "_")
        tag_dir = tags_dir / tag_normalized
        
        if not tag_dir.exists() or not tag_dir.is_dir():
            return {
                "files": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "pages": 0
            }
        
        # Get all .md files in tag directory
        files = sorted(
            tag_dir.glob("*.md"),
            key=lambda x: x.stat().st_mtime if x.exists() else 0,
            reverse=True
        )
        
        total_files = len(files)
        
        # Pagination
        start = (page - 1) * limit
        end = start + limit
        page_files = files[start:end]
        
        results = []
        for f in page_files:
            try:
                # Resolve symlink if it's a symlink
                if f.is_symlink():
                    actual_path = f.resolve()
                else:
                    actual_path = f
                
                if actual_path.exists():
                    stat = actual_path.stat()
                    results.append({
                        "name": f.name,
                        "path": str(actual_path),
                        "symlink_path": str(f) if f.is_symlink() else None,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
            except Exception as e:
                logger.warning(f"Error processing file {f.name}: {e}")
        
        return {
            "files": results,
            "total": total_files,
            "page": page,
            "limit": limit,
            "pages": (total_files + limit - 1) // limit if limit > 0 else 0,
            "tag": tag_normalized
        }
        
    except Exception as e:
        logger.error(f"Error getting files by tag {tag}: {e}")
        return {
            "files": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "pages": 0,
            "error": str(e)
        }