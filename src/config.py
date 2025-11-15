import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma")

if not OPENAI_API_KEY:
    print("⚠️ No OPENAI_API_KEY found in .env — ingestion and queries will fail.")

