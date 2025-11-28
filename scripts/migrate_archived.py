"""
Migration Script: Re-categorize Existing Archived Files
--------------------------------------------------------
One-time script to re-categorize existing files in knowledge/archived/
and move them to knowledge/archived/Auto/<category>/ subfolders.
"""

import logging
import shutil
from pathlib import Path

from scripts.config import config
from backend.utils.semantic_categorizer import categorize_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_archived_files():
    """Re-categorize and move existing archived files."""
    archive_dir = config.ARCHIVE
    
    if not archive_dir.exists():
        logger.info(f"Archive directory does not exist: {archive_dir}")
        return
    
    # Find all .md files in archive (excluding Auto/ subfolder)
    md_files = []
    for file_path in archive_dir.rglob("*.md"):
        # Skip files already in Auto/ subfolder
        if "Auto" in file_path.parts:
            continue
        md_files.append(file_path)
    
    if not md_files:
        logger.info("No files found to migrate")
        return
    
    logger.info(f"Found {len(md_files)} files to migrate")
    
    # Create Auto/ base directory
    auto_base = archive_dir / "Auto"
    auto_base.mkdir(parents=True, exist_ok=True)
    
    migrated_count = 0
    error_count = 0
    
    for file_path in md_files:
        try:
            logger.info(f"Processing: {file_path.name}")
            
            # Categorize file
            category = categorize_file(file_path)
            logger.info(f"  Category: {category}")
            
            # Create category subfolder
            category_dir = auto_base / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Move file to category folder
            target = category_dir / file_path.name
            
            # Handle duplicate filenames
            counter = 1
            while target.exists():
                name_parts = file_path.stem, file_path.suffix
                new_filename = f"{name_parts[0]}_{counter}{name_parts[1]}"
                target = category_dir / new_filename
                counter += 1
            
            shutil.move(str(file_path), str(target))
            logger.info(f"  Moved to: {target.relative_to(config.ROOT)}")
            migrated_count += 1
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            error_count += 1
    
    logger.info(f"\nMigration complete:")
    logger.info(f"  Migrated: {migrated_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Total: {len(md_files)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate archived files to semantic subfolders")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually moving files"
    )
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be moved")
        archive_dir = config.ARCHIVE
        md_files = [f for f in archive_dir.rglob("*.md") if "Auto" not in f.parts]
        logger.info(f"Would migrate {len(md_files)} files")
        for file_path in md_files[:10]:  # Show first 10
            try:
                category = categorize_file(file_path)
                logger.info(f"  {file_path.name} → Auto/{category}/")
            except Exception as e:
                logger.error(f"  {file_path.name} → ERROR: {e}")
        if len(md_files) > 10:
            logger.info(f"  ... and {len(md_files) - 10} more files")
    else:
        migrate_archived_files()

