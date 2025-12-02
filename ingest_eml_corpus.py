from pathlib import Path

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore
from legal_assistant.utils.chunking import chunk_text
from legal_assistant.utils.eml_extraction import extract_eml


def ingest_eml_corpus(
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

    for eml_file in raw_path.glob("*.eml"):
        total_files += 1
        print(f"\n[INFO] Processing EML file: {eml_file.name}")

        eml_data = extract_eml(eml_file)
        if not eml_data:
            print(f"[WARN] Skipping {eml_file.name} (no content extracted).")
            continue

        # Build a text representation that includes headers + body
        header_summary = (
            f"From: {eml_data['from']}\n"
            f"To: {eml_data['to']}\n"
            f"Subject: {eml_data['subject']}\n"
            f"Date: {eml_data['date']}\n\n"
        )
        full_text = header_summary + eml_data["body"]

        chunks = chunk_text(full_text, max_words=max_words, overlap=overlap)
        if not chunks:
            print(f"[WARN] No chunks created for {eml_file.name}")
            continue

        ids = []
        metadatas = []
        for i, _ in enumerate(chunks):
            chunk_id = f"{eml_file.stem}_chunk_{i}"
            ids.append(chunk_id)
            metadatas.append(
                {
                    "source_file": eml_file.name,
                    "chunk_index": i,
                    "source_type": "eml",
                    "from": eml_data["from"],
                    "to": eml_data["to"],
                    "subject": eml_data["subject"],
                    "date": eml_data["date"],
                }
            )

        print(f"[INFO] File {eml_file.name}: {len(chunks)} chunks")

        embeddings = embed_client.embed_texts(chunks)
        store.add_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        total_chunks += len(chunks)

    print("\n[DONE] EML ingestion complete.")
    print(f"  Total EML files processed: {total_files}")
    print(f"  Total EML chunks stored:   {total_chunks}")


if __name__ == "__main__":
    ingest_eml_corpus()
