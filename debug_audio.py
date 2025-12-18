"""Debug audio transcription with detailed logging."""
import os
import tempfile

print("Step 1: Testing temp file creation...")
tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
tmp_path = tmp_file.name
print(f"  Temp path: {tmp_path}")

print("Step 2: Writing data...")
test_data = b"fake audio test data" * 100
tmp_file.write(test_data)
print(f"  Wrote {len(test_data)} bytes")

print("Step 3: Flushing...")
tmp_file.flush()
print("  Flushed")

print("Step 4: Closing...")
tmp_file.close()
print("  Closed")

print("Step 5: Checking file exists...")
exists = os.path.exists(tmp_path)
print(f"  Exists: {exists}")

if exists:
    size = os.path.getsize(tmp_path)
    print(f"  Size: {size} bytes")
    
    print("Step 6: Trying to open for reading...")
    try:
        with open(tmp_path, "rb") as f:
            data = f.read(10)
            print(f"  Successfully read: {data[:10]}")
    except Exception as e:
        print(f"  ERROR reading: {e}")
    
    print("Step 7: Cleanup...")
    os.unlink(tmp_path)
    print("  Deleted")
else:
    print("  ERROR: File does not exist!")

print("\nNow testing with Whisper...")
from legal_assistant.utils.universal_extraction import _transcribe_audio_local

result = _transcribe_audio_local("test.mp3", test_data)
print(f"Result: {result.error if result.error else 'Success'}")
