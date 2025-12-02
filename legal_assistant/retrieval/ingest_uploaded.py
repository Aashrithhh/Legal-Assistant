from pathlib import Path
from typing import List, Tuple

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore
from legal_assistant.utils.chunking import chunk_text
from legal_assistant.utils.pdf_extraction import extract_text_from_pdf
from legal_assistant.utils.eml_extraction import extract_eml_from_bytes


def _extract_text_from_pdf_bytes(filename: str, data: bytes) -> str:
    tmp_path = Path(f"./tmp_{filename}")
    tmp_path.write_bytes(data)
    try:
        return extract_text_from_pdf(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _extract_text_from_txt_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def ingest_uploaded_files_into_vector_store(
    files: List[Tuple[str, bytes]],
    db_path: str = "data/index/embeddings.db",
    max_words: int = 200,
    overlap: int = 50,
) -> None:
    embed_client = EmbeddingClient()
    store = VectorStore(db_path=db_path)

    for filename, data in files:
        ext = Path(filename).suffix.lower()
        text = ""
        source_type = ""

        if ext == ".pdf":
            text = _extract_text_from_pdf_bytes(filename, data)
            source_type = "pdf"
        elif ext == ".txt":
            text = _extract_text_from_txt_bytes(data)
            source_type = "txt"
        elif ext == ".eml":
            eml_data = extract_eml_from_bytes(data)
            if not eml_data:
                print(f"[WARN] No usable content in uploaded email: {filename}")
                continue
            header = (
                f"From: {eml_data['from']}\n"
                f"To: {eml_data['to']}\n"
                f"Subject: {eml_data['subject']}\n"
                f"Date: {eml_data['date']}\n\n"
            )
            text = header + eml_data["body"]
            source_type = "eml"
        else:
            print(f"[WARN] Unsupported file type: {filename}")
            continue

        if not text.strip():
            print(f"[WARN] No text extracted from {filename}")
            continue

        chunks = chunk_text(text, max_words=max_words, overlap=overlap)

        ids = []
        metadatas = []
        stem = Path(filename).stem

        for i in range(len(chunks)):
            ids.append(f"upload_{stem}_chunk_{i}")
            metadatas.append({
                "source_file": filename,
                "chunk_index": i,
                "source_type": source_type,
            })

        embeddings = embed_client.embed_texts(chunks)
        store.add_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        print(f"[INFO] Ingested {filename} ({len(chunks)} chunks)")
