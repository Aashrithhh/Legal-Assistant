"""
Debug script to check what chunks are being retrieved for a query
and verify if audio chunks are included.
"""
import sys
from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore

def debug_retrieval(query_text: str, top_k: int = 100):
    """Show what chunks are retrieved for a given query."""
    print(f"=== Debugging Retrieval for Query ===")
    print(f"Query: {query_text[:200]}...")
    print(f"Top K: {top_k}\n")
    
    embed_client = EmbeddingClient()
    store = VectorStore(db_path="data/index/embeddings.db")
    
    # Embed query
    query_emb = embed_client.embed_texts([query_text])[0]
    
    # Retrieve
    retrieved = store.query_by_embedding(query_emb, top_k=top_k)
    
    # Analyze results
    audio_chunks = []
    text_chunks = []
    
    for idx, (_id, score, doc, meta) in enumerate(retrieved, start=1):
        source_file = meta.get("source_file", "unknown")
        source_type = meta.get("source_type", "unknown")
        chunk_index = meta.get("chunk_index", "unknown")
        
        entry = {
            "rank": idx,
            "file": source_file,
            "type": source_type,
            "chunk": chunk_index,
            "score": score,
            "text_preview": doc[:100]
        }
        
        if source_type == "audio" or source_file.endswith(".mp3"):
            audio_chunks.append(entry)
        else:
            text_chunks.append(entry)
    
    print(f"Total chunks retrieved: {len(retrieved)}")
    print(f"Audio chunks: {len(audio_chunks)}")
    print(f"Text chunks: {len(text_chunks)}\n")
    
    if audio_chunks:
        print("=== AUDIO CHUNKS FOUND ===")
        for entry in audio_chunks:
            print(f"Rank {entry['rank']}: {entry['file']} (score: {entry['score']:.4f})")
            print(f"  Type: {entry['type']}, Chunk: {entry['chunk']}")
            print(f"  Preview: {entry['text_preview']}...")
            print()
    else:
        print("⚠️  NO AUDIO CHUNKS IN TOP RESULTS")
        print("This means audio content has lower similarity scores than text documents.\n")
    
    print("=== TOP 10 TEXT CHUNKS ===")
    for entry in text_chunks[:10]:
        print(f"Rank {entry['rank']}: {entry['file']} (score: {entry['score']:.4f})")
        print(f"  Preview: {entry['text_preview']}...")
        print()

if __name__ == "__main__":
    # Use a simple query that should match the audio content
    test_query = """
Matter overview:
Potential discrimination and workplace misconduct involving Indian workers.
Reports of threats, monitoring, and retaliatory actions.

People and aliases:
William Davis, Francis Ham, Indian workers

Documents provided:
Multiple emails and audio recordings
"""
    
    debug_retrieval(test_query, top_k=100)
