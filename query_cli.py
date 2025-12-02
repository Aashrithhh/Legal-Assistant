from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore


def main():
    embed_client = EmbeddingClient()
    store = VectorStore(db_path="data/index/embeddings.db")

    print("=== Legal Search CLI (prototype) ===")
    print("Type a question about your case, or just press Enter to exit.\n")

    while True:
        query = input("Query> ").strip()
        if not query:
            print("Exiting.")
            break

        # 1) Embed the query
        query_embedding = embed_client.embed_texts([query])[0]

        # 2) Search in vector store
        results = store.query_by_embedding(query_embedding, top_k=5)

        if not results:
            print("No results found.\n")
            continue

        print(f"\nTop {len(results)} results:\n")
        for rank, (_id, score, doc, meta) in enumerate(results, start=1):
            source = meta.get("source_file", "unknown")
            chunk_index = meta.get("chunk_index", "n/a")
            print(f"Result #{rank}")
            print(f"  ID:          {_id}")
            print(f"  Score:       {score:.4f}")
            print(f"  Source file: {source}")
            print(f"  Chunk index: {chunk_index}")
            print("  Text:")
            print("   ", doc[:400].replace("\n", " "))
            print()

        print("-" * 60)


if __name__ == "__main__":
    main()
