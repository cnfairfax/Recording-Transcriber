# Recording Transcriber

A cross-platform desktop app that transcribes audio and video files using a **local [OpenAI Whisper](https://github.com/openai/whisper) model** — no cloud, no API key.

---

## Features

- **Drag & drop** audio/video files directly onto the app window
- **Local transcription** — all processing runs on your machine
- Supports `.mp3`, `.mp4`, `.wav`, `.flac`, `.m4a`, `.ogg`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.aac`, `.opus`, `.webm`, and more
- Choose Whisper model size (tiny → large)
- Language auto-detection or manual selection
- Output formats: **`.txt`**, **`.srt`** (subtitles), **`.vtt`** (WebVTT)
- Pick any folder to save transcripts — or save them next to the source files
- Cancel in-progress transcription
- Dark UI with status tracking per-file

---

## Prerequisites

1. **Python 3.9+** — https://www.python.org/downloads/
2. **ffmpeg** — required by Whisper to decode media files
   - Windows: `winget install ffmpeg` or https://ffmpeg.org/download.html
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

---

## Setup

```bash
# 1. Clone / open the repo
cd "Recording Transcriber"

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
#   Windows PowerShell:
.\.venv\Scripts\Activate.ps1
#   macOS / Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

> **Note:** The first time you run a transcription the selected Whisper model will be downloaded automatically (~74 MB for *base*, ~1.5 GB for *large*).

---

## Running the app

```bash
python app.py
```

---

## Usage

1. **Add files** — drag & drop them onto the drop zone, or click **Add Files…**
2. **Choose settings** — model size, language, output formats, output directory
3. Click **▶ Transcribe All** — the app transcribes each file in order
4. Transcripts are saved to the chosen folder (or next to each source file if no folder is set)

---

## Model sizes

| Model  | Size   | Notes                          |
|--------|--------|--------------------------------|
| tiny   | ~74 MB | Fastest; lower accuracy        |
| base   | ~142 MB| Good for quick drafts          |
| small  | ~244 MB| Balanced                       |
| medium | ~769 MB| High accuracy                  |
| large  | ~1.5 GB| Best accuracy; slow on CPU     |

For GPU acceleration install the appropriate PyTorch build for your CUDA version before installing the dependencies.

---

## License

MIT
