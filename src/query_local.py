import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src import rag_utils


if __name__ == "__main__":
    try:
        question = input("Ask your assistant (local Mistral): ")
    except KeyboardInterrupt:
        sys.exit(0)

    answer, metas, _ = rag_utils.answer_question(question)
    sources = rag_utils.format_sources(metas)
    if sources:
        answer += "\n\nSources:\n" + "\n".join(f"- {line}" for line in sources)
    print(answer)