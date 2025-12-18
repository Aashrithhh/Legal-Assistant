from pathlib import Path
from typing import List, Tuple, Dict, Any

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore
from legal_assistant.utils.chunking import chunk_text
from legal_assistant.utils.universal_extraction import extract_text_from_upload, ExtractedText


def ingest_uploaded_files_into_vector_store(
    files: List[Tuple[str, bytes]],
    db_path: str = "data/index/embeddings.db",
    max_words: int = 200,
    overlap: int = 40,
) -> Dict[str, Any]:
    """
    Ingest uploaded files into the vector store using universal extraction.
    
    Returns:
        {
            "ingested": [{"filename": str, "chunks": int, "source_type": str}],
            "failed": [{"filename": str, "reason": str}]
        }
    """
    embed_client = EmbeddingClient()
    store = VectorStore(db_path=db_path)

    ingested: List[Dict[str, Any]] = []
    failed: List[Dict[str, str]] = []

    for filename, data in files:
        # Use universal extraction
        extracted: ExtractedText = extract_text_from_upload(filename, data)
        
        # Check for extraction errors
        if extracted.error:
            print(f"[WARN] Extraction error for {filename}: {extracted.error}")
            failed.append({"filename": filename, "reason": extracted.error})
            continue
        
        text = extracted.text.strip()
        if not text:
            print(f"[WARN] No text extracted from {filename}")
            failed.append({"filename": filename, "reason": "empty extracted text"})
            continue

        # Chunk the text
        chunks = chunk_text(text, max_words=max_words, overlap=overlap)
        
        if not chunks:
            print(f"[WARN] No chunks created for {filename}")
            failed.append({"filename": filename, "reason": "no chunks created"})
            continue

        # Build IDs and metadata
        ids = []
        metadatas = []
        stem = Path(filename).stem

        for i in range(len(chunks)):
            ids.append(f"upload_{stem}_chunk_{i}")
            metadatas.append({
                "source_file": filename,
                "chunk_index": i,
                "source_type": extracted.source_type,
                **extracted.meta,  # Include extraction metadata
            })

        # Embed and store
        embeddings = embed_client.embed_texts(chunks)
        store.add_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        print(f"[INFO] Ingested {filename} ({len(chunks)} chunks, type: {extracted.source_type})")
        ingested.append({
            "filename": filename,
            "chunks": len(chunks),
            "source_type": extracted.source_type,
        })

    return {"ingested": ingested, "failed": failed}
