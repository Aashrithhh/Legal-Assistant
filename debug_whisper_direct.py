"""Debug what Whisper is actually doing."""
import os
import tempfile
import whisper
import traceback

# Create a valid temp audio file
tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
tmp_path = tmp_file.name
test_data = b"fake audio test data" * 100
tmp_file.write(test_data)
tmp_file.flush()
tmp_file.close()

print(f"Temp file: {tmp_path}")
print(f"Exists: {os.path.exists(tmp_path)}")
print(f"Size: {os.path.getsize(tmp_path)}")

print("\nLoading Whisper model...")
model = whisper.load_model("base")
print("Model loaded")

print("\nAttempting transcription...")
try:
    result = model.transcribe(tmp_path)
    print(f"Success! Text: {result['text'][:100]}")
except Exception as e:
    print(f"ERROR: {e}")
    print(f"Error type: {type(e).__name__}")
    print("\nFull traceback:")
    traceback.print_exc()

# Cleanup
try:
    os.unlink(tmp_path)
except:
    pass
