"""
Ragas evaluation runner.

Usage:
    pip install ragas datasets pandas
    python eval/run_ragas.py eval/sample_eval.csv
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_correctness,
    answer_similarity,
    faithfulness,
    context_precision,
    context_recall,
)


def main():
    parser = argparse.ArgumentParser(description="Run Ragas evaluation against CSV samples.")
    parser.add_argument("csv_path", help="CSV file with columns question,answer,context")
    parser.add_argument(
        "--output", default="eval/results.json", help="Where to write metric results (JSON)"
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    df = pd.read_csv(csv_path)
    if not {"question", "answer", "context"}.issubset(df.columns):
        raise ValueError("CSV must contain question, answer, context columns.")

    dataset = Dataset.from_pandas(df[["question", "answer", "context"]])
    result = evaluate(
        dataset,
        metrics=[
            answer_correctness,
            answer_similarity,
            faithfulness,
            context_precision,
            context_recall,
        ],
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

