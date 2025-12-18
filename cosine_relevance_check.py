import math
from typing import Dict, List, Tuple

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore

DB_PATH = "data/index/embeddings.db"  # same as the rest of your project


def map_score_to_category(score: float) -> str:
    """
    Map cosine similarity -> relevance bucket.
    Tune these thresholds if you want to be stricter/looser.
    """
    if score >= 0.70:
        return "highly_relevant"
    elif score >= 0.55:
        return "partially_relevant"
    elif score >= 0.45:
        return "less_relevant"
    else:
        return "not_relevant"


def main():
    print("=== Cosine Similarity Relevance Check (by file) ===\n")
    criteria = input("Enter Case Summary / Criteria: ").strip()
    if not criteria:
        print("No criteria entered. Exiting.")
        return

    # 1) Setup embedding client + vector store
    embed_client = EmbeddingClient()
    store = VectorStore(db_path=DB_PATH)

    # 2) Embed the criteria once
    query_emb = embed_client.embed_texts([criteria])[0]

    # 3) Retrieve a fairly large top_k so we see many chunks
    #    This uses your existing cosine-similarity search under the hood.
    results = store.query_by_embedding(query_emb, top_k=200)
    if not results:
        print("No chunks found in the vector store. Did you run ingest_* scripts?")
        return

    # 4) Aggregate: best score per source_file
    best_by_file: Dict[str, float] = {}
    for _id, score, doc, meta in results:
        fname = meta.get("source_file", "unknown")
        prev = best_by_file.get(fname)
        if prev is None or score > prev:
            best_by_file[fname] = score

    # 5) Sort files by score descending
    sorted_files: List[Tuple[str, float]] = sorted(
        best_by_file.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    # 6) Bucket into categories
    buckets: Dict[str, List[Tuple[str, float]]] = {
        "highly_relevant": [],
        "partially_relevant": [],
        "less_relevant": [],
        "not_relevant": [],
    }

    for fname, score in sorted_files:
        cat = map_score_to_category(score)
        buckets[cat].append((fname, score))

    # 7) Pretty-print results
    def print_bucket(title: str, key: str):
        items = buckets[key]
        print(f"\n{title} ({len(items)})")
        print("-" * 40)
        if not items:
            print("  (none)")
            return
        for fname, score in items:
            print(f"  {fname:40s}  score={score:.4f}")

    print_bucket("HIGHLY RELEVANT (>= 0.70)", "highly_relevant")
    print_bucket("PARTIALLY RELEVANT (0.55–0.69)", "partially_relevant")
    print_bucket("LESS RELEVANT (0.45–0.54)", "less_relevant")
    print_bucket("NOT RELEVANT (< 0.45)", "not_relevant")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
