from pathlib import Path

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore
from legal_assistant.utils.chunking import chunk_text


def ingest_txt_corpus(
    raw_dir: str = "data/raw_corpus",
    db_path: str = "data/index/embeddings.db",
    max_words: int = 200,
    overlap: int = 50,
) -> None:
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        print(f"[WARN] Raw corpus directory does not exist: {raw_path}")
        return

    embed_client = EmbeddingClient()
    store = VectorStore(db_path=db_path)

    total_files = 0
    total_chunks = 0

    for txt_file in raw_path.glob("*.txt"):
        total_files += 1
        print(f"\n[INFO] Processing file: {txt_file.name}")

        try:
            text = txt_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[ERROR] Failed to read {txt_file}: {e}")
            continue

        chunks = chunk_text(text, max_words=max_words, overlap=overlap)
        if not chunks:
            print(f"[WARN] No text/chunks extracted from {txt_file.name}")
            continue

        ids = []
        metadatas = []
        for i, _ in enumerate(chunks):
            chunk_id = f"{txt_file.stem}_chunk_{i}"
            ids.append(chunk_id)
            metadatas.append(
                {
                    "source_file": txt_file.name,
                    "chunk_index": i,
                }
            )

        print(f"[INFO] File {txt_file.name}: {len(chunks)} chunks")

        # Embed and store
        embeddings = embed_client.embed_texts(chunks)
        store.add_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        total_chunks += len(chunks)

    print("\n[DONE] Ingestion complete.")
    print(f"  Total files processed: {total_files}")
    print(f"  Total chunks stored:   {total_chunks}")


if __name__ == "__main__":
    ingest_txt_corpus()
