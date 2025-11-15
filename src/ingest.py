import glob
import hashlib
import os
import sys
from pathlib import Path
from typing import List

import chromadb
from sentence_transformers import SentenceTransformer

# Ensure package imports work when run as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.config import CHROMA_PATH

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = SentenceTransformer(MODEL_NAME)


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    if not text.strip():
        return []
    chunk_size = max(chunk_size, 1)
    chunk_overlap = max(min(chunk_overlap, chunk_size - 1), 0)
    chunks: List[str] = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_length:
            break
        start += chunk_size - chunk_overlap
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    return _model.encode(texts, normalize_embeddings=True).tolist()


def ingest_markdown_files(data_path: str = "data"):
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection("llm_docs")
    collection.delete()

    md_files = sorted(glob.glob(os.path.join(data_path, "*.md")))
    documents: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    for path in md_files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        for idx, chunk in enumerate(chunk_text(content)):
            documents.append(chunk)
            metadatas.append({"source": os.path.basename(path), "chunk": idx})
            ids.append(hashlib.md5(f"{path}-{idx}".encode("utf-8")).hexdigest())

    if not documents:
        print("[WARN] No markdown documents found. Nothing to embed.")
        return

    embeddings = embed_texts(documents)
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    print(f"Ingestion complete using {MODEL_NAME}.")


if __name__ == "__main__":
    ingest_markdown_files()
