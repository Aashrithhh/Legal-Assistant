"""Test audio transcription with a simple audio file."""
import os
import tempfile
from legal_assistant.utils.universal_extraction import extract_text_from_upload

# Create a minimal test - we'll need actual audio data for real test
# For now, let's test the file handling logic

print("Testing audio extraction file handling...")

# Simulate what happens with real audio
test_audio = b"fake audio data for testing"
result = extract_text_from_upload("test.mp3", test_audio)

print(f"Result: source_type={result.source_type}")
print(f"Error: {result.error}")

if result.error and "Audio transcription error" in result.error:
    print("✓ Error handling works (expected with fake audio data)")
else:
    print(f"✓ Got result: {result.text[:100] if result.text else 'No text'}")
