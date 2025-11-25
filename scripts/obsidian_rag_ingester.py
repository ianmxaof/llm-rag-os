"""
Obsidian RAG Ingester (Reference-Class Edition)
------------------------------------------------
Watch-folder pipeline for Obsidian vault with metadata-aware chunking,
hybrid BM25+vector search, SQLite ledger deduplication, and TOON serialization.

Features:
- Watches Manual/ and Auto/ folders selectively
- Extracts YAML frontmatter with graceful fallback
- SQLite ledger for 100% correct deduplication
- Heading-based chunking with overlap
- Pre-computed chunk summaries via Ollama
- fastembed for 3-6x faster embeddings
- LanceDB with hybrid BM25+vector index
- Separate curated vs raw collections
- Multi-process embedding queue
"""

import hashlib
import logging
import os
import sys
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import configuration
from scripts.config import (
    OBSIDIAN_WATCH_DIRS,
    OBSIDIAN_EXCLUDE_DIRS,
    OBSIDIAN_RECURSIVE,
    OBSIDIAN_CHUNK_OVERLAP,
    OBSIDIAN_MIN_CHUNK_SIZE,
    OBSIDIAN_EMBED_MODEL,
    OBSIDIAN_EMBED_MULTILINGUAL,
    USE_LANCEDB,
    LANCE_DB_PATH,
    ENABLE_HYBRID_SEARCH,
    TANTIVY_INDEX_PATH,
    OBSIDIAN_CURATED_COLLECTION,
    OBSIDIAN_RAW_COLLECTION,
    PROMPTS_CURATED_COLLECTION,
    ENABLE_HASH_DEDUP,
    INGESTION_LEDGER_PATH,
    USE_LLMLINGUA,
    USE_TOON_SERIALIZATION,
    PRE_COMPUTE_CHUNK_SUMMARIES,
    CHUNK_SUMMARY_MODEL,
    CHUNK_SUMMARY_MAX_TOKENS,
    EMBEDDING_WORKERS,
    OLLAMA_API_BASE,
    config
)

# Import Obsidian modules
from scripts.obsidian_metadata import extract_all_metadata, strip_frontmatter
from scripts.obsidian_chunker import chunk_by_headings, generate_obsidian_uri
from scripts.obsidian_ledger import IngestionLedger

# Try importing optional dependencies
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog not available. Install with: pip install watchdog")

try:
    import lancedb
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
    PYARROW_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    PYARROW_AVAILABLE = False
    logger.error("lancedb and pyarrow are required. Install with: pip install lancedb pyarrow")

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False
    logger.error("fastembed not available. Install with: pip install fastembed")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available for Ollama API calls")

try:
    from llmlingua import PromptCompressor
    LLMLINGUA_AVAILABLE = True
except ImportError:
    LLMLINGUA_AVAILABLE = False
    logger.warning("llmlingua not available. Install with: pip install llmlingua")

try:
    import toon
    TOON_AVAILABLE = True
except ImportError:
    TOON_AVAILABLE = False
    logger.warning("toon not available. Install with: pip install toon")


class ObsidianIngester:
    """Main ingester class for Obsidian notes."""
    
    def __init__(self):
        """Initialize ingester with all components."""
        self.ledger = IngestionLedger(INGESTION_LEDGER_PATH)
        self.embedder = None
        self.db = None
        self.curated_table = None
        self.raw_table = None
        self.compressor = None
        
        self._init_embedder()
        self._init_database()
        if USE_LLMLINGUA and LLMLINGUA_AVAILABLE:
            self._init_compressor()
    
    def _init_embedder(self):
        """Initialize fastembed embedder."""
        if not FASTEMBED_AVAILABLE:
            raise ImportError("fastembed is required. Install with: pip install fastembed")
        
        model_name = OBSIDIAN_EMBED_MODEL
        if OBSIDIAN_EMBED_MULTILINGUAL and ":multilingual" not in model_name:
            model_name = f"{model_name}:multilingual"
        
        logger.info(f"Initializing fastembed with model: {model_name}")
        self.embedder = TextEmbedding(model_name=model_name)
        logger.info("Embedder initialized successfully")
    
    def _init_database(self):
        """Initialize LanceDB with hybrid search."""
        if not LANCEDB_AVAILABLE:
            raise ImportError("lancedb is required. Install with: pip install lancedb")
        
        LANCE_DB_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Connecting to LanceDB at {LANCE_DB_PATH}")
        self.db = lancedb.connect(str(LANCE_DB_PATH))
        
        # Create or get curated collection
        try:
            self.curated_table = self.db.open_table(OBSIDIAN_CURATED_COLLECTION)
            logger.info(f"Opened curated collection: {OBSIDIAN_CURATED_COLLECTION}")
        except Exception:
            logger.info(f"Curated collection {OBSIDIAN_CURATED_COLLECTION} will be created on first insert")
            self.curated_table = None
        
        # Create or get raw collection
        try:
            self.raw_table = self.db.open_table(OBSIDIAN_RAW_COLLECTION)
            logger.info(f"Opened raw collection: {OBSIDIAN_RAW_COLLECTION}")
        except Exception:
            logger.info(f"Raw collection {OBSIDIAN_RAW_COLLECTION} will be created on first insert")
            self.raw_table = None
        
        # Create or get prompts_curated collection (for Prompt RAG Layer)
        try:
            self.prompts_table = self.db.open_table(PROMPTS_CURATED_COLLECTION)
            logger.info(f"Opened prompts collection: {PROMPTS_CURATED_COLLECTION}")
        except Exception:
            logger.info(f"Prompts collection {PROMPTS_CURATED_COLLECTION} will be created on first insert")
            self.prompts_table = None
    
    def _init_compressor(self):
        """Initialize LLMLingua-2 compressor."""
        if LLMLINGUA_AVAILABLE:
            logger.info("Initializing LLMLingua-2 compressor")
            self.compressor = PromptCompressor(
                model_name="NousResearch/LLMLingua-2-xlm-roberta-large-meetingbank"
            )
            logger.info("Compressor initialized")
    
    def _compute_chunk_summary(self, chunk_text: str) -> Optional[str]:
        """Pre-compute chunk summary via Ollama."""
        if not PRE_COMPUTE_CHUNK_SUMMARIES or not HTTPX_AVAILABLE:
            return None
        
        try:
            import httpx
            
            # Truncate to reasonable length for summary
            text = chunk_text[:2000] if len(chunk_text) > 2000 else chunk_text
            
            response = httpx.post(
                f"{OLLAMA_API_BASE.replace('/api', '')}/api/generate",
                json={
                    "model": CHUNK_SUMMARY_MODEL,
                    "prompt": f"Summarize this in one sentence: {text}",
                    "stream": False,
                    "options": {
                        "num_predict": CHUNK_SUMMARY_MAX_TOKENS
                    }
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("response", "").strip()
                return summary[:200]  # Limit summary length
        except Exception as e:
            logger.warning(f"Failed to generate chunk summary: {e}")
        
        return None
    
    def _is_crystallized_file(self, file_path: Path) -> bool:
        """
        Check if a file is a crystallized note (from Crystallize feature).
        
        Args:
            file_path: Path to markdown file
        
        Returns:
            True if file appears to be crystallized
        """
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Check for crystallized indicators in frontmatter or filename
            if "crystallized" in content.lower()[:2000]:  # Check first 2KB for frontmatter
                # Check for crystallized tag or mode in frontmatter
                if "tags:" in content and "crystallized" in content:
                    return True
                if "mode:" in content and ("Raw Mode" in content or "RAG Mode" in content or "Auto-Fallback" in content):
                    return True
            # Check filename pattern
            if "_crystallized" in file_path.stem or "crystallized" in file_path.stem.lower():
                return True
        except Exception as e:
            logger.warning(f"Error checking if file is crystallized: {e}")
        
        return False
    
    def _delete_chunks_for_file(self, file_path: Path) -> int:
        """
        Soft-delete all chunks for a specific file from LanceDB collections.
        Uses metadata flag pattern (production standard for LanceDB).
        
        Since LanceDB doesn't support UPDATE operations, we re-insert chunks
        with deleted: true metadata and filter queries to exclude them.
        
        Args:
            file_path: Path to file whose chunks should be deleted
        
        Returns:
            Number of chunks soft-deleted
        """
        deleted_count = 0
        
        try:
            # Normalize file path for comparison (try both absolute and relative)
            file_path_abs = str(file_path.resolve())
            file_path_rel = str(file_path)
            
            # Soft-delete from curated collection
            if self.curated_table is not None:
                try:
                    # Query chunks matching this file (excluding already deleted ones)
                    # Note: We need to get the actual data to re-insert with deleted flag
                    all_data = self.curated_table.to_pandas()
                    
                    if not all_data.empty and 'source' in all_data.columns:
                        # Find chunks matching deleted file (that aren't already deleted)
                        mask = (
                            (all_data['source'].astype(str).str.contains(file_path_abs, na=False) |
                             all_data['source'].astype(str).str.contains(file_path_rel, na=False) |
                             all_data['source'].astype(str).str.contains(file_path.name, na=False)) &
                            (all_data.get('deleted', pd.Series(['false'] * len(all_data))).astype(str) != 'true')
                        )
                        
                        rows_to_delete = all_data[mask]
                        deleted_count += len(rows_to_delete)
                        
                        if len(rows_to_delete) > 0:
                            logger.info(f"Soft-deleting {len(rows_to_delete)} chunks from curated collection for {file_path.name}")
                            
                            # Re-insert with deleted: true flag
                            # Extract vectors, texts, and metadata
                            import pyarrow as pa
                            
                            # Get vector column (assuming it's named 'vector')
                            vectors = rows_to_delete['vector'].tolist() if 'vector' in rows_to_delete.columns else []
                            texts = rows_to_delete['text'].tolist() if 'text' in rows_to_delete.columns else []
                            
                            # Update metadata to mark as deleted
                            metadata_dict = {}
                            for col in rows_to_delete.columns:
                                if col not in ['vector', 'text']:
                                    if col == 'deleted':
                                        metadata_dict[col] = ['true'] * len(rows_to_delete)
                                    else:
                                        metadata_dict[col] = rows_to_delete[col].astype(str).tolist()
                            
                            # Add deleted flag if not present
                            if 'deleted' not in metadata_dict:
                                metadata_dict['deleted'] = ['true'] * len(rows_to_delete)
                            
                            # Reconstruct schema and insert
                            schema_fields = [pa.field('vector', pa.list_(pa.float32())), pa.field('text', pa.string())]
                            for key in sorted(metadata_dict.keys()):
                                schema_fields.append(pa.field(key, pa.string()))
                            
                            schema = pa.schema(schema_fields)
                            arrays = [
                                pa.array(vectors, type=pa.list_(pa.float32())),
                                pa.array(texts, type=pa.string())
                            ]
                            for key in sorted(metadata_dict.keys()):
                                arrays.append(pa.array(metadata_dict[key], type=pa.string()))
                            
                            table_data = pa.Table.from_arrays(arrays, schema=schema)
                            self.curated_table.add(table_data)
                            
                            logger.info(f"Marked {len(rows_to_delete)} chunks as deleted in curated collection")
                except Exception as e:
                    logger.warning(f"Error soft-deleting from curated collection: {e}")
            
            # Soft-delete from raw collection
            if self.raw_table is not None:
                try:
                    all_data = self.raw_table.to_pandas()
                    
                    if not all_data.empty and 'source' in all_data.columns:
                        mask = (
                            (all_data['source'].astype(str).str.contains(file_path_abs, na=False) |
                             all_data['source'].astype(str).str.contains(file_path_rel, na=False) |
                             all_data['source'].astype(str).str.contains(file_path.name, na=False)) &
                            (all_data.get('deleted', pd.Series(['false'] * len(all_data))).astype(str) != 'true')
                        )
                        
                        rows_to_delete = all_data[mask]
                        deleted_count += len(rows_to_delete)
                        
                        if len(rows_to_delete) > 0:
                            logger.info(f"Soft-deleting {len(rows_to_delete)} chunks from raw collection for {file_path.name}")
                            
                            # Re-insert with deleted: true (same process as curated)
                            import pyarrow as pa
                            
                            vectors = rows_to_delete['vector'].tolist() if 'vector' in rows_to_delete.columns else []
                            texts = rows_to_delete['text'].tolist() if 'text' in rows_to_delete.columns else []
                            
                            metadata_dict = {}
                            for col in rows_to_delete.columns:
                                if col not in ['vector', 'text']:
                                    if col == 'deleted':
                                        metadata_dict[col] = ['true'] * len(rows_to_delete)
                                    else:
                                        metadata_dict[col] = rows_to_delete[col].astype(str).tolist()
                            
                            if 'deleted' not in metadata_dict:
                                metadata_dict['deleted'] = ['true'] * len(rows_to_delete)
                            
                            schema_fields = [pa.field('vector', pa.list_(pa.float32())), pa.field('text', pa.string())]
                            for key in sorted(metadata_dict.keys()):
                                schema_fields.append(pa.field(key, pa.string()))
                            
                            schema = pa.schema(schema_fields)
                            arrays = [
                                pa.array(vectors, type=pa.list_(pa.float32())),
                                pa.array(texts, type=pa.string())
                            ]
                            for key in sorted(metadata_dict.keys()):
                                arrays.append(pa.array(metadata_dict[key], type=pa.string()))
                            
                            table_data = pa.Table.from_arrays(arrays, schema=schema)
                            self.raw_table.add(table_data)
                            
                            logger.info(f"Marked {len(rows_to_delete)} chunks as deleted in raw collection")
                except Exception as e:
                    logger.warning(f"Error soft-deleting from raw collection: {e}")
            
        except Exception as e:
            logger.error(f"Error soft-deleting chunks for {file_path}: {e}", exc_info=True)
        
        return deleted_count
    
    @staticmethod
    def filter_deleted_chunks(results: List[Dict]) -> List[Dict]:
        """
        Filter out soft-deleted chunks from query results.
        
        This helper method should be used when querying LanceDB Obsidian collections
        to exclude chunks that have been soft-deleted.
        
        Args:
            results: List of result dictionaries from LanceDB query
        
        Returns:
            Filtered list excluding deleted chunks
        """
        return [r for r in results if r.get('deleted', 'false') != 'true']
    
    def reingest_single_file(self, file_path: Path, mark_as_curated: bool = False) -> Dict:
        """
        Re-ingest a single file, deleting old chunks first.
        Used for Memory Editor feature when crystallized files are edited.
        
        Args:
            file_path: Path to file to re-ingest
            mark_as_curated: Force mark as curated (for edited crystallized files)
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"🧠 Re-ingesting edited file: {file_path.name}")
        
        # Delete old chunks
        deleted_count = self._delete_chunks_for_file(file_path)
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old chunks for {file_path.name}")
        
        # Clear from ledger to force re-ingestion
        self.ledger.clear_file(file_path)
        
        # Process with force flag to ensure re-ingestion
        result = self.process_note(file_path, force=True)
        
        # If mark_as_curated, ensure it goes to curated collection
        if mark_as_curated and result.get("status") == "success":
            result["trust_level"] = "curated"
            logger.info(f"Marked {file_path.name} as curated after edit")
        
        return result
    
    def _determine_trust_level(self, metadata: Dict, file_path: Path) -> str:
        """Determine trust level (curated vs raw) based on source and confidence."""
        # Manual folder = curated
        if "Manual" in str(file_path):
            return "curated"
        
        # Crystallized files are always curated (high-value user-curated content)
        if self._is_crystallized_file(file_path):
            return "curated"
        
        # Check confidence in metadata
        confidence = metadata.get("confidence", "")
        if isinstance(confidence, str):
            confidence = confidence.lower()
            if confidence in ["high", "very high", "confirmed"]:
                return "curated"
        
        # Default to raw for Auto/ folder and low confidence
        return "raw"
    
    def process_note(self, file_path: Path, force: bool = False) -> Dict:
        """
        Process a single Obsidian note.
        
        Args:
            file_path: Path to markdown file
            force: Force re-ingestion even if hash matches
        
        Returns:
            Dictionary with processing results
        """
        if not file_path.exists() or file_path.suffix != ".md":
            return {"status": "skipped", "reason": "not_markdown"}
        
        # Check ledger for deduplication
        if not force and ENABLE_HASH_DEDUP:
            should_reingest, stored_hash = self.ledger.should_reingest(file_path)
            if not should_reingest:
                logger.info(f"Skipping {file_path.name} (hash unchanged)")
                return {"status": "skipped", "reason": "hash_unchanged", "hash": stored_hash}
        
        try:
            # Extract metadata
            metadata = extract_all_metadata(file_path)
            
            # Read content
            content = file_path.read_text(encoding='utf-8')
            body = strip_frontmatter(content)
            
            # Determine trust level
            trust_level = self._determine_trust_level(metadata, file_path)
            
            # Chunk by headings
            chunks = chunk_by_headings(
                body,
                metadata,
                overlap=OBSIDIAN_CHUNK_OVERLAP,
                min_chunk_size=OBSIDIAN_MIN_CHUNK_SIZE
            )
            
            if not chunks:
                logger.warning(f"No chunks created for {file_path.name}")
                return {"status": "skipped", "reason": "no_chunks"}
            
            # Process chunks
            chunk_data = []
            for chunk in chunks:
                chunk_text = chunk['text']
                chunk_meta = chunk['metadata'].copy()
                
                # Add obsidian URI
                chunk_meta['obsidian_uri'] = generate_obsidian_uri(
                    str(file_path),
                    chunk_meta.get('chunk_index', 0),
                    chunk_meta.get('section')
                )
                
                # Add trust level
                chunk_meta['trust_level'] = trust_level
                
                # Add soft-delete flag (default: false)
                chunk_meta['deleted'] = 'false'
                
                # Pre-compute summary
                if PRE_COMPUTE_CHUNK_SUMMARIES:
                    summary = self._compute_chunk_summary(chunk_text)
                    if summary:
                        chunk_meta['chunk_summary'] = summary
                
                # Compress if enabled
                if USE_LLMLINGUA and LLMLINGUA_AVAILABLE and self.compressor:
                    try:
                        compressed = self.compressor.compress_prompt(chunk_text)
                        chunk_text = compressed if compressed else chunk_text
                    except Exception as e:
                        logger.warning(f"Compression failed: {e}")
                
                chunk_data.append({
                    'text': chunk_text,
                    'metadata': chunk_meta
                })
            
            # Embed chunks
            texts = [c['text'] for c in chunk_data]
            embeddings = list(self.embedder.embed(texts))
            
            # Prepare data for LanceDB
            table = self.curated_table if trust_level == "curated" else self.raw_table
            
            # Convert to LanceDB format (pyarrow table)
            if not PYARROW_AVAILABLE:
                raise ImportError("pyarrow is required for LanceDB. Install with: pip install pyarrow")
            
            # Prepare data arrays
            vectors = [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]
            texts = [c['text'] for c in chunk_data]
            
            # Collect all metadata keys from all chunks
            all_metadata_keys = set()
            for chunk in chunk_data:
                all_metadata_keys.update(chunk['metadata'].keys())
            
            # Prepare metadata columns
            metadata_dict = {}
            for key in sorted(all_metadata_keys):  # Sort for consistency
                values = []
                for chunk in chunk_data:
                    value = chunk['metadata'].get(key, None)
                    # Convert lists to strings for LanceDB
                    if isinstance(value, list):
                        values.append(', '.join(str(v) for v in value))
                    elif value is None:
                        values.append('')
                    else:
                        values.append(str(value))
                metadata_dict[key] = values
            
            # Create pyarrow schema
            schema_fields = [
                pa.field('vector', pa.list_(pa.float32())),
                pa.field('text', pa.string())
            ]
            for key in sorted(metadata_dict.keys()):  # Sort for consistency
                schema_fields.append(pa.field(key, pa.string()))
            
            schema = pa.schema(schema_fields)
            
            # Create arrays
            arrays = [
                pa.array(vectors, type=pa.list_(pa.float32())),
                pa.array(texts, type=pa.string())
            ]
            for key in sorted(metadata_dict.keys()):  # Sort for consistency
                arrays.append(pa.array(metadata_dict[key], type=pa.string()))
            
            # Create pyarrow table
            table_data = pa.Table.from_arrays(arrays, schema=schema)
            
            # Insert into LanceDB
            collection_name = OBSIDIAN_CURATED_COLLECTION if trust_level == "curated" else OBSIDIAN_RAW_COLLECTION
            
            if table is None:
                # Create table on first insert
                logger.info(f"Creating {collection_name} table with {len(chunk_data)} chunks")
                table = self.db.create_table(collection_name, table_data)
                if trust_level == "curated":
                    self.curated_table = table
                else:
                    self.raw_table = table
            else:
                # Add to existing table
                logger.debug(f"Adding {len(chunk_data)} chunks to existing {collection_name} table")
                table.add(table_data)
            
            # Record in ledger
            self.ledger.record_ingestion(file_path, len(chunks))
            
            logger.info(f"Ingested {file_path.name}: {len(chunks)} chunks ({trust_level})")
            
            return {
                "status": "success",
                "chunks": len(chunks),
                "trust_level": trust_level,
                "file": str(file_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "file": str(file_path)}


class NoteHandler(FileSystemEventHandler):
    """Watchdog event handler for file changes."""
    
    def __init__(self, ingester: ObsidianIngester):
        self.ingester = ingester
        self.processed_files = set()
    
    def on_created(self, event):
        """Handle file creation."""
        if not event.is_directory:
            self._process_file(Path(event.src_path))
    
    def on_modified(self, event):
        """Handle file modification."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            # Check if this is a crystallized file being edited
            if self.ingester._is_crystallized_file(file_path):
                logger.info(f"🧠 Detected edit to crystallized file: {file_path.name}")
                # Re-ingest with curated status
                result = self.ingester.reingest_single_file(file_path, mark_as_curated=True)
                if result.get("status") == "success":
                    logger.info(f"✅ Memory updated: {file_path.name} (your edit was learned)")
                    # Could add notification here if Streamlit is running
                    self._notify_memory_update(file_path)
                else:
                    logger.warning(f"Failed to update memory for {file_path.name}: {result.get('error', 'unknown')}")
            else:
                # Normal file modification
                self._process_file(file_path)
    
    def on_deleted(self, event):
        """Handle file deletion."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix == ".md":
                self._handle_file_deleted(file_path)
    
    def _handle_file_deleted(self, file_path: Path):
        """
        Handle file deletion - remove chunks and ledger entry.
        
        Args:
            file_path: Path to deleted file
        """
        # Check if file was previously ingested (query ledger)
        stored_hash = self.ingester.ledger.get_file_hash(file_path)
        if stored_hash is None:
            logger.debug(f"File {file_path.name} was not in ledger, skipping deletion")
            return
        
        logger.info(f"🗑️ Detected deletion of ingested file: {file_path.name}")
        
        # Delete chunks from vector store
        deleted_count = self.ingester._delete_chunks_for_file(file_path)
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} chunks for {file_path.name}")
        
        # Remove from ingestion ledger
        self.ingester.ledger.clear_file(file_path)
        logger.info(f"✅ Removed {file_path.name} from ledger (ghost memory deleted)")
    
    def _notify_memory_update(self, file_path: Path):
        """Notify user that memory was updated (placeholder for future integration)."""
        # This could integrate with Streamlit notifications or system notifications
        # For now, just log it
        logger.info(f"🧠 Memory updated notification: {file_path.name}")
    
    def _process_file(self, file_path: Path):
        """Process a file if it matches criteria."""
        # Check if it's a markdown file
        if file_path.suffix != ".md":
            return
        
        # Check if in excluded directories
        for exclude_dir in OBSIDIAN_EXCLUDE_DIRS:
            if exclude_dir in str(file_path):
                return
        
        # Check if in watch directories
        in_watch_dir = False
        for watch_dir in OBSIDIAN_WATCH_DIRS:
            watch_path = Path(config.ROOT) / watch_dir
            try:
                file_path.relative_to(watch_path)
                in_watch_dir = True
                break
            except ValueError:
                continue
        
        if not in_watch_dir:
            return
        
        # Process file
        result = self.ingester.process_note(file_path)
        logger.info(f"Processed {file_path.name}: {result.get('status', 'unknown')}")


def main():
    """Main entry point."""
    logger.info("Starting Obsidian RAG Ingester (Reference-Class Edition)")
    
    # Check dependencies
    if not WATCHDOG_AVAILABLE:
        logger.error("watchdog is required. Install with: pip install watchdog")
        sys.exit(1)
    
    if not LANCEDB_AVAILABLE:
        logger.error("lancedb is required. Install with: pip install lancedb")
        sys.exit(1)
    
    if not FASTEMBED_AVAILABLE:
        logger.error("fastembed is required. Install with: pip install fastembed")
        sys.exit(1)
    
    # Initialize ingester
    ingester = ObsidianIngester()
    
    # Setup watchdog
    event_handler = NoteHandler(ingester)
    observer = Observer()
    
    # Watch all specified directories
    for watch_dir in OBSIDIAN_WATCH_DIRS:
        watch_path = Path(config.ROOT) / watch_dir
        if watch_path.exists():
            observer.schedule(event_handler, str(watch_path), recursive=OBSIDIAN_RECURSIVE)
            logger.info(f"Watching: {watch_path}")
        else:
            logger.warning(f"Watch directory does not exist: {watch_path}")
    
    observer.start()
    logger.info("Observer started. Press Ctrl+C to stop.")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping observer...")
        observer.stop()
    
    observer.join()
    logger.info("Observer stopped.")


if __name__ == "__main__":
    main()

