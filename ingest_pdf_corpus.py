from pathlib import Path

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore
from legal_assistant.utils.chunking import chunk_text
from legal_assistant.utils.pdf_extraction import extract_text_from_pdf


def ingest_pdf_corpus(
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

    for pdf_file in raw_path.glob("*.pdf"):
        total_files += 1
        print(f"\n[INFO] Processing PDF file: {pdf_file.name}")

        text = extract_text_from_pdf(pdf_file)
        if not text:
            print(f"[WARN] Skipping {pdf_file.name} (no text extracted).")
            continue

        chunks = chunk_text(text, max_words=max_words, overlap=overlap)
        if not chunks:
            print(f"[WARN] No chunks created for {pdf_file.name}")
            continue

        ids = []
        metadatas = []
        for i, _ in enumerate(chunks):
            chunk_id = f"{pdf_file.stem}_chunk_{i}"
            ids.append(chunk_id)
            metadatas.append(
                {
                    "source_file": pdf_file.name,
                    "chunk_index": i,
                    "source_type": "pdf",
                }
            )

        print(f"[INFO] File {pdf_file.name}: {len(chunks)} chunks")

        embeddings = embed_client.embed_texts(chunks)
        store.add_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        total_chunks += len(chunks)

    print("\n[DONE] PDF ingestion complete.")
    print(f"  Total PDF files processed: {total_files}")
    print(f"  Total PDF chunks stored:   {total_chunks}")


if __name__ == "__main__":
    ingest_pdf_corpus()
