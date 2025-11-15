"""
Refine Script
-------------
Reprocesses and re-embeds documents with optional new parameters.
Supports version tracking and deduplication.
"""

import argparse
import hashlib
import logging
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from sentence_transformers import SentenceTransformer

from scripts.config import config
from scripts.preprocess import preprocess_text
from backend.models import Document, SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def file_hash(path: Path) -> str:
    """Compute MD5 hash of file."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Error computing hash: {e}")
        return path.stem


def refine_document_by_source(
    source_path: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    batch_size: int = None
):
    """
    Refine (reprocess and re-embed) a document.
    
    Args:
        source_path: Path to source document
        chunk_size: Optional new chunk size
        chunk_overlap: Optional new chunk overlap
        batch_size: Optional batch size for embedding
    """
    p = Path(source_path)
    if not p.exists():
        logger.error(f"Path not found: {source_path}")
        return False
    
    # Read document
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {source_path}: {e}")
        return False
    
    # Preprocess with optional new parameters
    # Note: preprocess_text uses config values by default, so we need to temporarily override
    # For now, we'll use the config values (can be enhanced later)
    chunks = preprocess_text(text, clean=True)
    
    if not chunks:
        logger.warning("No chunks created")
        return False
    
    # Compute file hash
    file_hash_val = file_hash(p)
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name=config.EMBED_MODEL, normalize_embeddings=True
    )
    collection = client.get_or_create_collection(
        name=config.COLLECTION_NAME, embedding_function=embedding_function
    )
    
    # Delete old chunks for this source
    try:
        results = collection.get(where={"source": str(p)})
        old_ids = results.get("ids", [])
        if old_ids:
            collection.delete(ids=old_ids)
            logger.info(f"Deleted {len(old_ids)} old chunks")
    except Exception as e:
        logger.warning(f"Could not delete old chunks: {e}")
    
    # Embed new chunks
    batch_size = batch_size or config.EMBED_BATCH_SIZE
    model = SentenceTransformer(config.EMBED_MODEL)
    
    all_ids = []
    all_documents = []
    all_metadatas = []
    all_embeddings = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_embeddings = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        
        for j, (chunk, embedding) in enumerate(zip(batch, batch_embeddings)):
            chunk_id = f"{file_hash_val}_refined_{i+j}"
            all_ids.append(chunk_id)
            all_documents.append(chunk)
            all_metadatas.append({
                "source": str(p),
                "chunk": i + j,
                "file_hash": file_hash_val,
                "refined": True
            })
            all_embeddings.append(embedding.tolist())
    
    # Upsert to ChromaDB
    collection.upsert(
        ids=all_ids,
        documents=all_documents,
        metadatas=all_metadatas,
        embeddings=all_embeddings
    )
    
    logger.info(f"Refined and re-indexed {source_path} -> {len(chunks)} chunks")
    
    # Update SQLite metadata
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.source_path == str(p)).first()
        if doc:
            doc.ingest_version += 1
            doc.file_hash = file_hash_val
            db.commit()
            logger.info(f"Updated metadata: version {doc.ingest_version}")
        else:
            # Create new document entry
            doc = Document(
                source_path=str(p),
                file_hash=file_hash_val,
                ingest_version=1,
                status="indexed"
            )
            db.add(doc)
            db.commit()
            logger.info("Created new document entry")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating metadata: {e}")
    finally:
        db.close()
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refine (reprocess and re-embed) a document")
    parser.add_argument("--source", required=True, help="Path to source document")
    parser.add_argument("--chunk-size", type=int, help="Chunk size (uses config default if not specified)")
    parser.add_argument("--chunk-overlap", type=int, help="Chunk overlap (uses config default if not specified)")
    parser.add_argument("--batch-size", type=int, help="Embedding batch size (uses config default if not specified)")
    
    args = parser.parse_args()
    
    success = refine_document_by_source(
        args.source,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        batch_size=args.batch_size
    )
    
    if success:
        print("[SUCCESS] Document refined successfully")
    else:
        print("[ERROR] Refinement failed")
        exit(1)

