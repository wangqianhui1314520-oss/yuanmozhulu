"""Merge narration audio into video using ffmpeg."""
import subprocess
import os

VIDEO = r"d:\AI\元末逐鹿\videos\yuanmo-promo\renders\video.mp4"
AUDIO = r"d:\AI\元末逐鹿\videos\yuanmo-promo\audio\narration_full.mp3"
OUTPUT = r"d:\AI\元末逐鹿\videos\yuanmo-promo\renders\video_with_audio.mp4"
SPED_AUDIO = r"d:\AI\元末逐鹿\videos\yuanmo-promo\audio\narration_sped.mp3"

FFMPEG = r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"

# Step 1: Speed up audio to match video duration
# Video is 77s, audio is 88.46s → atempo = 88.46/77 ≈ 1.149
print("Step 1: Speeding up audio (atempo=1.149)...")
result = subprocess.run([
    FFMPEG, "-y",
    "-i", AUDIO,
    "-filter:a", "atempo=1.149",
    "-c:a", "libmp3lame", "-q:a", "2",
    SPED_AUDIO
], capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR:", result.stderr[-500:])
    exit(1)
print("OK")

# Step 2: Merge audio with video
print("Step 2: Merging audio into video...")
result = subprocess.run([
    FFMPEG, "-y",
    "-i", VIDEO,
    "-i", SPED_AUDIO,
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", "192k",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-shortest",
    OUTPUT
], capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR:", result.stderr[-500:])
    exit(1)
print("OK")

# Clean up temp file
os.remove(SPED_AUDIO)

# Check output
size_mb = os.path.getsize(OUTPUT) / (1024*1024)
print(f"\nDone! {OUTPUT}")
print(f"Size: {size_mb:.1f} MB")

# Verify duration
result = subprocess.run([
    FFMPEG, "-v", "error",
    "-show_entries", "format=duration",
    "-of", "csv=p=0",
    OUTPUT
], capture_output=True, text=True)
print(f"Duration: {float(result.stdout.strip()):.1f}s")
