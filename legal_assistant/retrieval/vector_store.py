from typing import List, Dict, Any, Tuple
import os
import sqlite3
import json
import math


class VectorStore:
    """
    Very simple vector store backed by SQLite.

    - Stores one row per chunk:
        id TEXT PRIMARY KEY
        embedding TEXT (JSON-encoded list[float])
        document TEXT
        metadata TEXT (JSON-encoded dict)

    - Query is brute-force: we load all embeddings and compute cosine similarity.
      This is fine for a prototype and thousands of chunks.
    """

    def __init__(self, db_path: str = "data/index/embeddings.db") -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    id TEXT PRIMARY KEY,
                    embedding TEXT NOT NULL,
                    document TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]] | None = None,
    ) -> None:
        if metadatas is None:
            metadatas = [{} for _ in ids]

        if not (len(ids) == len(embeddings) == len(documents) == len(metadatas)):
            raise ValueError("ids, embeddings, documents, metadatas must have same length")

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            for _id, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
                cur.execute(
                    """
                    INSERT OR REPLACE INTO embeddings (id, embedding, document, metadata)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        _id,
                        json.dumps(emb),
                        doc,
                        json.dumps(meta),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for x, y in zip(a, b):
            dot += x * y
            norm_a += x * x
            norm_b += y * y
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / math.sqrt(norm_a * norm_b)

    def query_by_embedding(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        boost_audio: bool = True,
    ) -> List[Tuple[str, float, str, Dict[str, Any]]]:
        """
        Returns a list of (id, score, document, metadata_dict) sorted by score desc.
        
        If boost_audio=True (default), audio chunks are always included in results
        with artificially boosted scores to ensure they appear in the context for citation.
        This is critical for legal compliance as audio recordings are primary evidence.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, embedding, document, metadata FROM embeddings")
            rows = cur.fetchall()
        finally:
            conn.close()

        audio_results: List[Tuple[str, float, str, Dict[str, Any]]] = []
        text_results: List[Tuple[str, float, str, Dict[str, Any]]] = []
        
        for _id, emb_json, doc, meta_json in rows:
            emb = json.loads(emb_json)
            meta = json.loads(meta_json) if meta_json else {}
            score = self._cosine_similarity(query_embedding, emb)
            
            # Check if this is an audio source
            source_type = meta.get("source_type", "")
            source_file = meta.get("source_file", "")
            is_audio = (source_type == "audio" or 
                       source_file.endswith(".mp3") or 
                       source_file.endswith(".wav") or 
                       source_file.endswith(".m4a"))
            
            if is_audio:
                # Boost audio scores by 2x to ensure they rank higher
                boosted_score = score * 2.0 if boost_audio else score
                audio_results.append((_id, boosted_score, doc, meta))
            else:
                text_results.append((_id, score, doc, meta))
        
        # Sort both lists by score (descending)
        audio_results.sort(key=lambda x: x[1], reverse=True)
        text_results.sort(key=lambda x: x[1], reverse=True)
        
        # Combine: prioritize audio chunks, then fill with text chunks
        combined = audio_results + text_results
        
        return combined[:top_k]
