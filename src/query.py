import sys
from pathlib import Path

import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer

# Ensure package imports work when run as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.config import CHROMA_PATH, OPENAI_API_KEY

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = SentenceTransformer(MODEL_NAME)


def query_rag(question: str):
    client = OpenAI(api_key=OPENAI_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection("llm_docs")

    query_embedding = _model.encode([question], normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=3)
    if not results["documents"]:
        return "I couldn't find any relevant context in your knowledge base."

    context = " ".join(results["documents"][0])
    prompt = f"Answer this question using context:\n\n{context}\n\nQuestion: {question}"
    completion = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content.strip()


if __name__ == "__main__":
    question = input("❓ Ask your assistant: ")
    print(query_rag(question))
