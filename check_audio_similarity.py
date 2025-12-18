"""
Check the embedding quality and similarity scores for audio chunks directly.
"""
import sqlite3
import json
from legal_assistant.llm.embeddings_client import EmbeddingClient

def check_audio_embeddings():
    """Verify audio chunks exist and test their similarity to a relevant query."""
    
    db_path = "data/index/embeddings.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get audio chunks
    cursor.execute("""
        SELECT id, document, metadata 
        FROM embeddings 
        WHERE metadata LIKE '%mp3%' OR id LIKE '%william%' OR id LIKE '%francis%'
    """)
    
    audio_chunks = cursor.fetchall()
    
    if not audio_chunks:
        print("❌ No audio chunks found in database!")
        return
    
    print(f"✅ Found {len(audio_chunks)} audio chunks\n")
    
    embed_client = EmbeddingClient()
    
    # Test queries that should match audio content
    test_queries = [
        "threats of deportation return home immigration",
        "monitor workers surveillance email",
        "discrimination against Indian workers",
    ]
    
    for chunk_id, document, metadata_json in audio_chunks:
        metadata = json.loads(metadata_json)
        source_file = metadata.get("source_file", "unknown")
        
        print(f"=== Audio Chunk: {source_file} ===")
        print(f"Chunk ID: {chunk_id}")
        print(f"Text: {document}")
        print()
        
        # Get embedding for this document
        doc_emb = embed_client.embed_texts([document])[0]
        
        print("Similarity scores to test queries:")
        for query in test_queries:
            query_emb = embed_client.embed_texts([query])[0]
            
            # Compute cosine similarity manually
            import numpy as np
            similarity = np.dot(doc_emb, query_emb) / (np.linalg.norm(doc_emb) * np.linalg.norm(query_emb))
            
            print(f"  '{query}': {similarity:.4f}")
        
        print("\n" + "="*80 + "\n")
    
    conn.close()
    
    # Now compare to a typical email chunk
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, document, metadata 
        FROM embeddings 
        WHERE metadata LIKE '%aiR0000003235%'
        LIMIT 1
    """)
    
    email_chunk = cursor.fetchone()
    if email_chunk:
        chunk_id, document, metadata_json = email_chunk
        metadata = json.loads(metadata_json)
        source_file = metadata.get("source_file", "unknown")
        
        print(f"=== Comparison: Email Chunk {source_file} ===")
        print(f"Text length: {len(document)} chars")
        print(f"Preview: {document[:200]}...")
        print()
        
        doc_emb = embed_client.embed_texts([document])[0]
        
        print("Similarity scores to test queries:")
        for query in test_queries:
            query_emb = embed_client.embed_texts([query])[0]
            import numpy as np
            similarity = np.dot(doc_emb, query_emb) / (np.linalg.norm(doc_emb) * np.linalg.norm(query_emb))
            print(f"  '{query}': {similarity:.4f}")

if __name__ == "__main__":
    check_audio_embeddings()
