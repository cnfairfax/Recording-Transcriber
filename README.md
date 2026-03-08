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

The source code of this project is released under the **MIT License**.

> **Note on PyQt6:** The GUI framework used by this application, [PyQt6](https://riverbankcomputing.com/software/pyqt/), is licensed under the **GNU GPL v3**. As a result, any binary distribution of this application that includes PyQt6 is subject to the terms of the GPL v3. The MIT license applies to the original source files in this repository only.

---

## Open Source Acknowledgements

This application is built on the following open source libraries and models. Each is used in accordance with its license terms.

### faster-whisper
CTranslate2-based reimplementation of OpenAI Whisper.
- Repository: https://github.com/SYSTRAN/faster-whisper
- License: **MIT**

### OpenAI Whisper (models)
Speech recognition models developed by OpenAI, used via faster-whisper.
- Repository: https://github.com/openai/whisper
- License: **MIT**

### CTranslate2
Efficient inference engine for Transformer models, used internally by faster-whisper.
- Repository: https://github.com/OpenNMT/CTranslate2
- License: **MIT**

### PyQt6
Python bindings for the Qt application framework, providing the desktop GUI.
- Website: https://riverbankcomputing.com/software/pyqt/
- License: **GNU GPL v3** (commercial license also available from Riverbank Computing)

### Intel OpenVINO
Hardware acceleration toolkit for Intel CPUs, GPUs, and Neural Processing Units.
- Repository: https://github.com/openvinotoolkit/openvino
- License: **Apache License 2.0**

### ffmpeg
Audio and video decoding, used to read media files before transcription. Not bundled — must be installed separately.
- Website: https://ffmpeg.org
- License: **GNU LGPL v2.1+** (some components licensed under GPL — see https://ffmpeg.org/legal.html)

### PyInstaller *(build-time only)*
Packages the application into a standalone executable. Not included in the distributed application.
- Website: https://pyinstaller.org
- License: **GPL v2 with a bootloader exception** (the exception permits the packaged application itself to remain under its own license)
