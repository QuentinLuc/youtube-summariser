"""Download a YouTube video's audio and transcribe it locally with mlx-whisper.

Writes to <out_dir>:
  metadata.json    yt-dlp metadata (title, description, chapters, language)
  transcript.json  mlx-whisper output (timestamped segments)
  input.md         prompt.md filled with both, ready to give to Claude

Usage:
  python3 transcribe.py <url> <out_dir> [--focus TEXT] [--language CODE]
                        [--cookies-from-browser BROWSER]

Needs uv (tools run through uv/uvx, nothing installed globally), node (yt-dlp solves
YouTube's JS challenge with it) and ffmpeg on PATH (mlx-whisper decodes the audio with it).
Audio is kept in a temporary directory and deleted afterwards.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from fill_prompt import fill, suspect_spans

HERE = Path(__file__).parent
# Whisper only reads the last ~224 tokens of the initial prompt.
GLOSSARY_MAX_CHARS = 600
# Capitalised words that are not names or terms, even when they appear mid-title.
GLOSSARY_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "how", "what", "why",
    "is", "are", "it", "its", "you", "your", "we", "our", "my", "i", "this", "that", "these", "learn",
    "more", "here", "if", "when", "from", "by", "be", "can", "do", "does", "doesn't", "about", "as",
    "but", "not", "no", "new", "who", "all", "same", "time", "hands", "meet", "compare",
}


def run(name: str, cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # The tool's own stderr is the only useful diagnosis (e.g. a YouTube bot check).
        sys.exit(f"{name} failed (exit {result.returncode}):\n{result.stderr.strip()[-2000:]}")
    return result


def yt_dlp(url: str, cookies_from_browser: str | None, *args: str) -> subprocess.CompletedProcess:
    # YouTube serves media only after a JS challenge; without a JS runtime and the
    # solver scripts ([default] extra), downloads intermittently fail with HTTP 403.
    # --ignore-config: a user-level yt-dlp config must not change what this script does.
    cmd = ["uvx", "--from", "yt-dlp[default]", "yt-dlp", "--ignore-config", "--js-runtimes", "node", *args]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    # "--" so a URL starting with "-" can never be read as an option.
    return run("yt-dlp", [*cmd, "--", url])


def detect_language(meta: dict) -> str | None:
    # yt-dlp reports e.g. "fr-FR"; Whisper wants "fr". None lets Whisper detect it.
    language = meta.get("language")
    return language.split("-")[0] if language else None


def build_glossary(meta: dict) -> str:
    # Names and terms Whisper is likely to mishear, taken from what the uploader wrote, as a
    # comma-separated list. Not sentences: a sentence at the head of the prompt (the title) is a
    # phrase Whisper can latch onto and repeat instead of transcribing.
    description = re.sub(r"https?://\S+", " ", meta.get("description") or "")
    chunks = [meta.get("title") or "", meta.get("channel") or "",
              *(c.get("title") or "" for c in meta.get("chapters") or []),
              *re.split(r"[.!?:\n•→|–-]\s", description)]
    seen, terms = set(), []
    for chunk in chunks:
        for i, word in enumerate(re.findall(r"[A-Za-z][\w'’]*[A-Za-z0-9]", chunk)):
            inner_caps = any(ch.isupper() for ch in word[1:]) or any(ch.isdigit() for ch in word)  # IBM, LLMs, TypeSafe
            mid_capital = i > 0 and word[0].isupper()  # capitalised, but not because it starts a chunk
            rest = chunk[chunk.find(word) + len(word):].lstrip()
            name_start = word[0].isupper() and rest[:1].isupper()  # "Martin Keen"
            is_channel = chunk == meta.get("channel")
            if not (inner_caps or mid_capital or name_start or is_channel):
                continue
            if word.lower() in GLOSSARY_STOPWORDS or word.lower() in seen:
                continue
            seen.add(word.lower())
            terms.append(word)
    glossary = ""
    for term in terms:
        if len(glossary) + len(term) + 2 > GLOSSARY_MAX_CHARS:
            break
        glossary = f"{glossary}, {term}" if glossary else term
    return glossary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--focus", default="general", help="reader focus for the prompt")
    parser.add_argument("--language", help="override the language yt-dlp reports, e.g. 'en'")
    parser.add_argument("--cookies-from-browser", help="e.g. 'chrome', when YouTube blocks the download")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("1/3 metadata")
    meta = json.loads(yt_dlp(args.url, args.cookies_from_browser, "--skip-download", "--dump-json").stdout)
    (args.out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        print("2/3 audio")
        # Native format (webm/m4a), no conversion: mlx-whisper decodes and resamples with ffmpeg itself.
        yt_dlp(args.url, args.cookies_from_browser, "-f", "bestaudio", "-o", str(tmp_dir / "audio.%(ext)s"))
        audio_files = [p for p in tmp_dir.glob("audio.*") if p.suffix != ".part"]
        if not audio_files:
            sys.exit("yt-dlp reported success but wrote no audio file")
        audio_path = audio_files[0]

        print("3/3 transcription")
        language = args.language or detect_language(meta)
        run("mlx-whisper", [
            "uv", "run", "--quiet", "--no-project", "--with", "mlx-whisper",
            "python", str(HERE / "whisper_run.py"),
            str(audio_path), str(args.out_dir / "transcript.json"), build_glossary(meta),
            *([language] if language else []),
        ])

    segments = json.loads((args.out_dir / "transcript.json").read_text())["segments"]
    (args.out_dir / "input.md").write_text(fill(meta, segments, args.focus))
    spans = suspect_spans(segments)
    print(f"done: {len(segments)} segments, {len(spans)} suspect span(s), "
          f"language={language or 'auto'} -> {args.out_dir}")


if __name__ == "__main__":
    main()
