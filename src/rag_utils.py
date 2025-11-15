import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
import requests
from sentence_transformers import SentenceTransformer

ROOT_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = ROOT_DIR / "chroma"

EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
LOCAL_MODEL_ID = os.getenv("LOCAL_MODEL_ID", "mistral-7b-instruct-v0.2")
LOCAL_MODEL_URL = os.getenv(
    "LOCAL_MODEL_URL", "http://127.0.0.1:1234/v1/chat/completions"
)
DEFAULT_K = int(os.getenv("RAG_TOP_K", "3"))
LOCAL_MODEL_TIMEOUT = float(os.getenv("LOCAL_MODEL_TIMEOUT", "120"))


@lru_cache(maxsize=1)
def _get_embedder() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL_NAME)


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = _get_embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection("llm_docs")


def retrieve_context(
    question: str, k: int = DEFAULT_K
) -> Tuple[str, List[Dict], List[str]]:
    collection = _get_collection()
    query_embedding = embed_texts([question])
    results = collection.query(query_embeddings=query_embedding, n_results=k)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    formatted = format_context(documents, metadatas)
    return formatted, metadatas, documents


def format_context(docs: List[str], metas: List[Dict]) -> str:
    parts: List[str] = []
    for idx, (doc, meta) in enumerate(zip(docs, metas), start=1):
        title = meta.get("title") or "Untitled"
        source = meta.get("source") or "unknown"
        chunk = meta.get("chunk", idx - 1)
        parts.append(f"[{idx}] {title} (chunk {chunk})\nSource: {source}\n{doc}")
    return "\n\n".join(parts)


PROMPT_TEMPLATE = """You are a helpful assistant. Use the numbered context chunks below to answer the question.

Context:
{context}

Instructions:
- Cite chunk numbers (e.g., [1], [2]) in your answer.
- If you do not have enough information, say you are unsure.

Question: {question}
Answer:"""


def build_messages(question: str, context: str) -> List[Dict]:
    user_message = PROMPT_TEMPLATE.format(context=context, question=question)
    return [{"role": "user", "content": user_message}]


def call_local_model(messages: List[Dict]) -> str:
    response = requests.post(
        LOCAL_MODEL_URL,
        headers={"Content-Type": "application/json"},
        json={"model": LOCAL_MODEL_ID, "messages": messages},
        timeout=LOCAL_MODEL_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def answer_question(question: str, k: int = DEFAULT_K) -> Tuple[str, List[Dict], str]:
    context, metas, _ = retrieve_context(question, k=k)
    messages = build_messages(question, context)
    answer = call_local_model(messages)
    return answer, metas, context


def format_sources(metas: List[Dict]) -> List[str]:
    sources: List[str] = []
    for idx, meta in enumerate(metas, start=1):
        title = meta.get("title") or "Untitled"
        source = meta.get("source") or "unknown"
        chunk = meta.get("chunk")
        label = f"[{idx}] {title}"
        if chunk is not None:
            label += f" (chunk {chunk})"
        label += f" — {source}"
        sources.append(label)
    return sources

