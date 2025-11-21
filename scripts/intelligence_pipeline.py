"""
Intelligence Pipeline
---------------------
Main orchestrator for the intelligence OS pipeline.
Coordinates: collect → refine → scan → ingest
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.collectors import GitHubCollector, RSSCollector, ArxivCollector, RedditCollector
from backend.services.refinement import RefinementService
from backend.services.secret_scanner import SecretScanner
from backend.services.ingestion_queue import IngestionQueue
from backend.models import Source, SourceItem, RefinedDocument, SecretScan, init_db, SessionLocal
from scripts.config import config


def collect_from_sources(since: datetime = None) -> List[Dict]:
    """
    Collect items from all enabled sources.
    
    Args:
        since: Only collect items newer than this timestamp
        
    Returns:
        List of collected items
    """
    db = SessionLocal()
    all_items = []
    
    try:
        # Get all enabled sources
        sources = db.query(Source).filter(Source.enabled == True).all()
        
        for source in sources:
            print(f"[INFO] Collecting from {source.name} ({source.source_type})...")
            
            # Get appropriate collector
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
                print(f"[WARN] Unknown source type: {source.source_type}")
                continue
            
            # Collect items
            items = collector.collect(since=since or source.last_collected)
            print(f"  → Collected {len(items)} items")
            
            # Save to database
            for item in items:
                source_item = SourceItem(
                    source_id=source.id,
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    url=item.get("url", ""),
                    published_at=item.get("published_at"),
                    raw_data=item.get("raw_data", {}),
                )
                db.add(source_item)
                all_items.append({
                    "source_item": source_item,
                    "item_data": item,
                })
            
            # Update source
            source.last_collected = datetime.utcnow()
            source.items_collected += len(items)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Collection failed: {e}")
    finally:
        db.close()
    
    return all_items


def refine_items(items: List[Dict]) -> List[Dict]:
    """
    Refine collected items using LLM curation.
    
    Args:
        items: List of items with source_item and item_data
        
    Returns:
        List of refined items
    """
    refinement_service = RefinementService()
    refined_items = []
    
    print(f"[INFO] Refining {len(items)} items...")
    
    for item_data in items:
        source_item = item_data["source_item"]
        item = item_data["item_data"]
        
        # Skip if already refined
        db = SessionLocal()
        try:
            existing = db.query(RefinedDocument).filter(
                RefinedDocument.source_item_id == source_item.id
            ).first()
            if existing:
                continue
        finally:
            db.close()
        
        # Refine item
        refined = refinement_service.refine_item(item)
        
        if refined:
            print(f"  → Refined: {refined['title'][:50]}... (permanence: {refined['permanence']})")
            refined_items.append({
                "source_item": source_item,
                "refined": refined,
            })
        else:
            print(f"  → SKIPped: {item.get('title', '')[:50]}...")
    
    return refined_items


def scan_for_secrets(items: List[Dict]) -> List[Dict]:
    """
    Scan items for secrets.
    
    Args:
        items: List of refined items
        
    Returns:
        List of items with scan results
    """
    scanner = SecretScanner()
    scanned_items = []
    
    print(f"[INFO] Scanning {len(items)} items for secrets...")
    
    for item_data in items:
        source_item = item_data["source_item"]
        refined = item_data["refined"]
        
        # Scan content
        content = refined.get("content", "") or refined.get("summary", "")
        scan_result = scanner.scan_text(content, source_url=refined.get("source_url"))
        
        if scan_result["found"]:
            print(f"  ⚠ Secrets found in: {refined.get('source_url', '')[:50]}...")
            scanner.send_alert(scan_result["secrets"], refined.get("source_url"))
            
            # Save scan result
            db = SessionLocal()
            try:
                secret_scan = SecretScan(
                    source_item_id=source_item.id,
                    source_url=refined.get("source_url", ""),
                    secrets_found=scan_result["secrets"],
                    alerted=True,
                )
                db.add(secret_scan)
                db.commit()
            finally:
                db.close()
            
            # Use redacted content
            refined["content"] = scan_result["redacted_text"]
        
        scanned_items.append({
            **item_data,
            "scan_result": scan_result,
        })
    
    return scanned_items


def save_refined_items(items: List[Dict]):
    """
    Save refined items to database and queue for ingestion.
    
    Args:
        items: List of refined items with scan results
    """
    db = SessionLocal()
    queue = IngestionQueue()
    
    print(f"[INFO] Saving {len(items)} refined items...")
    
    try:
        for item_data in items:
            source_item = item_data["source_item"]
            refined = item_data["refined"]
            
            # Save refined document
            refined_doc = RefinedDocument(
                source_item_id=source_item.id,
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
            
            # Mark source item as refined
            source_item.refined = True
            
            # Add to ingestion queue
            queue.add_item(refined)
            
            # Write markdown file for Path A compatibility
            output_dir = Path(config.ROOT) / "intelligence-data" / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            markdown_content = f"""---
title: {refined['title']}
permanence: {refined['permanence']}
entities: {refined.get('entities', '')}
tags: {refined.get('tags', [])}
source: {refined['source_url']}
date: {datetime.now().strftime('%Y-%m-%d')}
---

# {refined['title']}

**Source**: [link]({refined['source_url']})

**Entities**: {refined.get('entities', '')}

{refined.get('content', '')[:3000]}
"""
            
            # Create safe filename
            safe_title = "".join(c for c in refined['title'][:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{safe_title}_{refined['permanence']}.md"
            output_path = output_dir / filename
            
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"  → Saved: {filename}")
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to save refined items: {e}")
    finally:
        db.close()


def run_pipeline(since: datetime = None):
    """
    Run the complete intelligence pipeline.
    
    Args:
        since: Only process items newer than this timestamp
    """
    print("=" * 60)
    print("Intelligence Pipeline - Starting")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # Step 1: Collect
    items = collect_from_sources(since=since)
    print(f"[INFO] Collected {len(items)} items total")
    
    if not items:
        print("[INFO] No new items to process")
        return
    
    # Step 2: Refine
    refined_items = refine_items(items)
    print(f"[INFO] Refined {len(refined_items)} items (SKIPped {len(items) - len(refined_items)})")
    
    if not refined_items:
        print("[INFO] No items passed refinement")
        return
    
    # Step 3: Scan for secrets
    scanned_items = scan_for_secrets(refined_items)
    
    # Step 4: Save and queue
    save_refined_items(scanned_items)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print("=" * 60)
    print(f"Pipeline complete in {elapsed:.1f}s")
    print(f"  → Collected: {len(items)}")
    print(f"  → Refined: {len(refined_items)}")
    print(f"  → Saved: {len(scanned_items)}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Intelligence OS Pipeline")
    parser.add_argument(
        "--since-hours",
        type=int,
        default=None,
        help="Only process items from last N hours"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database tables"
    )
    
    args = parser.parse_args()
    
    if args.init_db:
        init_db()
        print("[INFO] Database initialized")
        sys.exit(0)
    
    since = None
    if args.since_hours:
        since = datetime.now() - timedelta(hours=args.since_hours)
    
    run_pipeline(since=since)

