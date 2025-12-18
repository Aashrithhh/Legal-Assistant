"""Check what chunks were stored for the mp3 files."""
import sqlite3
import json

DB = "data/index/embeddings.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Get mp3 chunks
cur.execute("""
    SELECT id, metadata, document 
    FROM embeddings 
    WHERE metadata LIKE '%mp3%' OR metadata LIKE '%william%' OR metadata LIKE '%francis%'
""")

rows = cur.fetchall()
print(f"Found {len(rows)} chunks for mp3 files\n")

for row in rows:
    chunk_id, meta_json, doc_text = row
    
    try:
        meta = json.loads(meta_json)
    except:
        meta = {"raw": meta_json}
    
    print("="*60)
    print(f"Chunk ID: {chunk_id}")
    print(f"Source file: {meta.get('source_file', 'unknown')}")
    print(f"Source type: {meta.get('source_type', 'unknown')}")
    print(f"Chunk index: {meta.get('chunk_index', 'unknown')}")
    print(f"Transcription method: {meta.get('transcription_method', 'N/A')}")
    print(f"Language: {meta.get('language', 'N/A')}")
    print(f"\nDocument text:")
    print(doc_text)
    print()

conn.close()

if len(rows) == 0:
    print("No mp3 chunks found. The audio files may not have been ingested yet.")
    print("Make sure to:")
    print("1. Start backend with ffmpeg in PATH")
    print("2. Upload the mp3 files through the UI")
    print("3. Wait for transcription to complete")
