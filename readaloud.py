#!/usr/bin/env python3
"""
readaloud - Local text-to-speech for websites, PDFs, and DOCX files.

All processing is fully local. No data leaves the machine.
Requires: pyttsx3, requests, beautifulsoup4, pymupdf, python-docx
"""

import argparse
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_from_url(url: str) -> str:
    """Fetch a web page and return its readable text."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        sys.exit("Missing dependencies. Run: pip install requests beautifulsoup4")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        sys.exit(f"Could not fetch URL: {exc}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "button", "input", "select",
                     "textarea", "noscript", "iframe"]):
        tag.decompose()

    # Prefer <article> / <main> when available
    content = soup.find("article") or soup.find("main") or soup.body or soup

    text = content.get_text(separator="\n")
    return _clean_text(text)


def extract_from_pdf(path: Path) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("Missing dependency. Run: pip install pymupdf")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        sys.exit(f"Could not open PDF: {exc}")

    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()

    return _clean_text("\n".join(pages))


def extract_from_docx(path: Path) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        from docx import Document
    except ImportError:
        sys.exit("Missing dependency. Run: pip install python-docx")

    try:
        doc = Document(str(path))
    except Exception as exc:
        sys.exit(f"Could not open DOCX: {exc}")

    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return _clean_text("\n".join(paragraphs))


def _clean_text(text: str) -> str:
    """Normalise whitespace and remove junk characters."""
    # Replace non-breaking spaces and other unicode spaces
    text = text.replace("\xa0", " ").replace("\u200b", "")
    # Collapse runs of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse runs of spaces/tabs
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# TTS engine
# ---------------------------------------------------------------------------

class Speaker:
    """Thin wrapper around pyttsx3 with interactive controls."""

    def __init__(self, rate: int, volume: float, voice_index: Optional[int]):
        try:
            import pyttsx3
        except ImportError:
            sys.exit("Missing dependency. Run: pip install pyttsx3")

        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", max(0.0, min(1.0, volume)))

        voices = self._engine.getProperty("voices")
        if voices and voice_index is not None:
            if voice_index < len(voices):
                self._engine.setProperty("voice", voices[voice_index].id)
            else:
                print(
                    f"Voice index {voice_index} out of range "
                    f"({len(voices)} voices available). Using default.",
                    file=sys.stderr,
                )

    def list_voices(self) -> None:
        voices = self._engine.getProperty("voices")
        if not voices:
            print("No voices found on this system.")
            return
        for i, v in enumerate(voices):
            print(f"  [{i}]  id={v.id}  name={v.name}  lang={getattr(v, 'languages', '?')}")

    def speak(self, text: str, chunk_size: int = 5000) -> None:
        """Speak text in chunks so the user can interrupt with Ctrl-C."""
        chunks = _split_into_chunks(text, chunk_size)
        total = len(chunks)
        print(f"Reading {total} chunk(s). Press Ctrl-C to stop.\n")

        for i, chunk in enumerate(chunks, 1):
            print(f"[{i}/{total}] {chunk[:80].strip()}{'…' if len(chunk) > 80 else ''}")
            try:
                self._engine.say(chunk)
                self._engine.runAndWait()
            except KeyboardInterrupt:
                self._engine.stop()
                print("\nStopped.")
                return

        print("\nDone.")


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries, keeping chunks under max_chars."""
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) > max_chars and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence) + 1

    if current:
        chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Source detection
# ---------------------------------------------------------------------------

def detect_source(source: str) -> str:
    """Return 'url', 'pdf', 'docx', or raise an error."""
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        return "url"

    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in (".docx", ".doc"):
        return "docx"

    # Try to guess from content if extension is missing
    if path.exists():
        header = path.read_bytes()[:8]
        if header[:4] == b"%PDF":
            return "pdf"
        # DOCX is a ZIP starting with PK
        if header[:2] == b"PK":
            return "docx"

    sys.exit(
        f"Cannot determine file type for '{source}'. "
        "Supported: URLs (http/https), .pdf, .docx"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="readaloud",
        description=(
            "Read websites, PDFs, or DOCX files aloud using local TTS.\n"
            "All processing is fully local — no data leaves the machine."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="URL (https://…), path to a .pdf file, or path to a .docx file.",
    )
    parser.add_argument(
        "--rate", type=int, default=175,
        help="Speech rate in words per minute (default: 175).",
    )
    parser.add_argument(
        "--volume", type=float, default=1.0,
        help="Volume from 0.0 (silent) to 1.0 (full, default: 1.0).",
    )
    parser.add_argument(
        "--voice", type=int, default=None, metavar="INDEX",
        help="Voice index to use (see --list-voices).",
    )
    parser.add_argument(
        "--list-voices", action="store_true",
        help="List available TTS voices and exit.",
    )
    parser.add_argument(
        "--dump-text", action="store_true",
        help="Print extracted text to stdout instead of speaking it.",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=5000, metavar="CHARS",
        help="Max characters per TTS chunk (default: 5000).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    speaker = Speaker(rate=args.rate, volume=args.volume, voice_index=args.voice)

    if args.list_voices:
        speaker.list_voices()
        return

    if not args.source:
        parser.print_help()
        sys.exit(1)

    # --- Extract text ---
    source_type = detect_source(args.source)
    print(f"Source type: {source_type}  |  {args.source}", file=sys.stderr)

    if source_type == "url":
        text = extract_from_url(args.source)
    elif source_type == "pdf":
        text = extract_from_pdf(Path(args.source))
    else:
        text = extract_from_docx(Path(args.source))

    if not text:
        sys.exit("No text could be extracted from the source.")

    print(f"Extracted {len(text):,} characters.", file=sys.stderr)

    if args.dump_text:
        print(text)
        return

    speaker.speak(text, chunk_size=args.chunk_size)


if __name__ == "__main__":
    main()
