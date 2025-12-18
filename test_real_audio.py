"""Test transcription of actual audio files."""
from legal_assistant.utils.universal_extraction import extract_text_from_upload
import os

audio_files = [
    r"data\raw_corpus\aiRwilliam.mp3",
    r"data\raw_corpus\aiRfrancis.mp3"
]

for audio_path in audio_files:
    if not os.path.exists(audio_path):
        print(f"❌ File not found: {audio_path}")
        continue
    
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(audio_path)}")
    print(f"Size: {os.path.getsize(audio_path) / 1024:.1f} KB")
    print(f"{'='*60}")
    
    with open(audio_path, "rb") as f:
        data = f.read()
    
    result = extract_text_from_upload(os.path.basename(audio_path), data)
    
    if result.error:
        print(f"❌ Error: {result.error}")
    else:
        print(f"✅ Success!")
        print(f"Source type: {result.source_type}")
        print(f"Metadata: {result.meta}")
        print(f"Transcription length: {len(result.text)} characters")
        print(f"\nFirst 500 characters:")
        print(result.text[:500])
        if len(result.text) > 500:
            print("...")
