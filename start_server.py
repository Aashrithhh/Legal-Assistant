"""
Start the FastAPI server with ffmpeg in PATH.
"""
import os
import sys
import subprocess

# Refresh PATH to include ffmpeg
machine_path = os.environ.get('PATH', '')
try:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment') as key:
        machine_path = winreg.QueryValueEx(key, 'PATH')[0]
except:
    pass

try:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment') as key:
        user_path = winreg.QueryValueEx(key, 'PATH')[0]
        machine_path = machine_path + ";" + user_path
except:
    pass

os.environ['PATH'] = machine_path

# Verify ffmpeg is available
import shutil
ffmpeg_path = shutil.which('ffmpeg')
if ffmpeg_path:
    print(f"✓ ffmpeg found at: {ffmpeg_path}")
else:
    print("⚠ WARNING: ffmpeg not found in PATH. Audio transcription will not work.")
    print("  Install: winget install ffmpeg")
    print("  Then restart this script.")

# Start uvicorn
print("\nStarting FastAPI server...")
print("API will be available at: http://localhost:8000")
print("Press Ctrl+C to stop\n")

subprocess.run([
    sys.executable, "-m", "uvicorn", 
    "api_server:app", 
    "--reload", 
    "--host", "0.0.0.0", 
    "--port", "8000"
])
