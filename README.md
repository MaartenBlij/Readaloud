# readaloud

A fully local, privacy-first text-to-speech tool for websites, PDFs, and DOCX files.

**No data ever leaves the machine.** No cloud APIs, no LLMs, no telemetry.

---

## Supported input types

| Source | How to pass it |
|--------|----------------|
| Web page | Full URL starting with `http://` or `https://` |
| PDF | Path to a `.pdf` file |
| Word document | Path to a `.docx` file |

---

## Requirements

| Platform | TTS engine | How to get it |
|----------|-----------|---------------|
| macOS | Built-in `say` command | Nothing to install |
| Linux | `espeak-ng` | `sudo apt install espeak-ng` (or see install.sh) |

Python 3.9 or later is required.

---

## Setup

```bash
git clone <this-repo>
cd readaloud
bash install.sh
```

`install.sh` will:
1. Install `espeak-ng` via your system package manager (Linux only).
2. Create a Python virtual environment in `.venv/`.
3. Install all Python dependencies from `requirements.txt`.
4. Generate a `run_readaloud.sh` convenience wrapper.

---

## Usage

```bash
# Read a web page
./run_readaloud.sh https://en.wikipedia.org/wiki/Text-to-speech

# Read a PDF
./run_readaloud.sh ~/Documents/report.pdf

# Read a Word document
./run_readaloud.sh ~/Documents/contract.docx

# Slower rate, louder, specific voice
./run_readaloud.sh --rate 140 --volume 0.9 --voice 1 report.pdf

# List available voices on this machine
./run_readaloud.sh --list-voices

# Print extracted text to stdout (no audio)
./run_readaloud.sh --dump-text report.pdf
```

### All options

```
positional arguments:
  source                URL (https://…), .pdf file, or .docx file

options:
  --rate INT            Words per minute (default: 175)
  --volume FLOAT        0.0 – 1.0 (default: 1.0)
  --voice INDEX         Voice index from --list-voices
  --list-voices         List available voices and exit
  --dump-text           Print extracted text instead of speaking
  --chunk-size CHARS    Max chars per TTS chunk (default: 5000)
```

Press **Ctrl-C** at any time to stop playback.

---

## How it works

```
Source
  │
  ├─ URL   → requests + BeautifulSoup  → plain text
  ├─ PDF   → PyMuPDF (fitz)            → plain text
  └─ DOCX  → python-docx               → plain text
                │
                ▼
         text cleaning / chunking
                │
                ▼
         pyttsx3  →  macOS: say
                  →  Linux: espeak-ng
```

All libraries run entirely on-device. `pyttsx3` is a thin Python wrapper that
delegates to the OS speech engine — no model files are downloaded at runtime.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `pyttsx3` | Cross-platform TTS (wraps `say` / `espeak-ng`) |
| `requests` | HTTP client for web pages |
| `beautifulsoup4` | HTML parsing and text extraction |
| `lxml` | Fast HTML parser for BeautifulSoup |
| `pymupdf` | PDF text extraction |
| `python-docx` | DOCX text extraction |

---

## Troubleshooting

**No audio on Linux**
- Check that `espeak-ng` is installed: `espeak-ng --version`
- Check audio output: `aplay /usr/share/sounds/alsa/Front_Center.wav`
- Try a different voice: `./run_readaloud.sh --list-voices`

**Web page reads too much noise**
The extractor prefers `<article>` / `<main>` tags. For heavily JavaScript-rendered
pages the static HTML fetch may yield limited text. In that case, save the page
as PDF from your browser and pass the PDF path instead.

**PDF text is garbled**
Some PDFs are scan-only images without a text layer. You need an OCR step first
(e.g. `ocrmypdf input.pdf output.pdf`) before passing the file to readaloud.
