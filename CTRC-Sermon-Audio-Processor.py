docstring = """
Requirements:
- You must be running a recent enough version of Windows to run ffmpeg.
- You must have ffmpeg installed and added to the user or system path.

Setup:
1. Go to: https://github.com/BtbN/FFmpeg-Builds/releases
2. Download and unzip the "GPL, static" build (ex. "ffmpeg-n9.0-latest-win64-gpl-9.0.zip").
3. Copy the path to the "bin" directory in the unzipped build.
4. Search for "path" in the Windows menu.
5. Select the "Edit the system environment variables" option from "Control panel".
6. Select "Environment Variables..." in the bottom right.
7. In the lower scroll view, find and double click the "Path" row.
8. Select "New" and paste the path you copied in step 3.

Usage: Drag a .wav file and a .png file onto the app.
"""

# Build with:
# py -m PyInstaller --onefile ".\CTRC-Sermon-Audio-Processor.py"

import re
import subprocess
import sys
import time

def stopWithError(e: str):
    print(e, file=sys.stderr)
    input()
    exit(1)

# Check if ffmpeg is on the path
try:
    result = subprocess.run(
        ["ffmpeg", "-h"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        stopWithError(docstring)
except:
    stopWithError(docstring)

# Search input arguments for the expected single .png and single .wav
audio = None
cover = None

for path in sys.argv[1:]:
    if path.endswith(".wav"):
        if audio != None:
            stopWithError("Multiple .wav file inputs. Only use 1 at a time.")
        audio = path
    elif path.endswith(".png"):
        if cover != None:
            stopWithError("Multiple .png file inputs. Only use 1 at a time.")
        cover = path
    else:
        stopWithError("Only .wav and .png files are supported.")

if audio == None:
    stopWithError("Expected a .wav file input.")
if cover == None:
    stopWithError("Expected a .png file input.")

# Windows can be annoying with backslashes, so use forward slashes
audio = audio.replace("\\", "/")
cover = cover.replace("\\", "/")

# Prompt the user for an output path or use the .wav file's name, but as .mp4
default_output = audio[:-3] + "mp4"
print(f"Enter an output path...")
print(f"(leave empty for default '{default_output}')")
output = input(f"Output path: ")
if output == "":
    output = default_output

# Find the loudest sample from the audio clip
result = subprocess.run(
    ["ffmpeg", "-i", audio, "-af", "volumedetect", "-f", "null", "-"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)

if result.returncode != 0:
    stopWithError(f"ffmpeg failed with exit code {result.returncode}.")

# Parse ffmpeg's search for the volume result
regex = re.compile(r"max_volume: (-?\d+\.?\d*) dB")
maxVolumeLine: re.Match = re.search(regex, result.stdout)

if not maxVolumeLine:
    maxVolumeLine = re.search(regex, result.stderr)

if not maxVolumeLine:
    stopWithError(f"Could not find 'max_volume' value in ffmpeg output")

maxVolume = float(maxVolumeLine.group(1))

# Gain as necessary to make the loudest sample be -1dB
gain = -1 - maxVolume
print(f"Volume of max amplitude sample from audio file determined to be: {maxVolume} dB")
print(f"Using gain of {gain} dB to normalize audio volume to -1 dB")

# Gain and combine the audio clip with the cover image
print(f"Combining...\n\tcover {cover} and...\n\taudio {audio} into...\n\tvideo {output}")

# Search ffmpeg's output for the total duration of the audio clip
# This is used later to track completion progress
duration_match = re.search(
    r"Duration:\s*(\d+):(\d+):([\d.]+)",
    result.stderr,
)
duration = None
if duration_match:
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

# Run ffmpeg and while it is running, capture each progress update
start_time = time.monotonic()
process = subprocess.Popen(
    [
        "ffmpeg",
        "-y",  # overwrite output without confirmation
        "-v", "warning",
        "-nostats",
        "-progress", "pipe:1",
        "-loop", "1",
        "-i", cover,
        "-i", audio,
        "-vf", "format=yuv420p",
        "-c:v", "libx264",
        "-crf", "18",
        "-af", f"volume={gain}",
        "-shortest",
        output,
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace",
)

# Parse the progress updates from ffmpeg to track completion percentage
progress_time = 0
for line in process.stdout:
    key, separator, value = line.partition("=")
    if separator and (key == "out_time_us"):
        # FFmpeg reports both of these timestamp fields in microseconds.
        progress_time = int(value) / 1_000_000
        elapsed_time = time.monotonic() - start_time
        if duration:
            percent = min(progress_time / duration * 100, 100)
            print(
                f"\rProgress: {percent:6.2f}% | Elapsed: {elapsed_time:.1f}s",
                end="",
                flush=True,
            )
        else:
            print(
                f"\rProcessed: {progress_time:.1f}s | Elapsed: {elapsed_time:.1f}s",
                end="",
                flush=True,
            )

print()
returncode = process.wait()
elapsed_time = time.monotonic() - start_time

if returncode != 0:
    stopWithError(f"ffmpeg failed with exit code {returncode}.")

print(f"Success. Output written to: {output} (completed in {elapsed_time:.1f}s)")

input("Press Enter to exit...")
