"""Fill prompt.md from yt-dlp metadata and an mlx-whisper JSON transcript.

Usage: python3 fill_prompt.py <metadata.json> <transcript.json> <focus> > filled.md
"""
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
# Closing tags of the prompt's data blocks. Escaped in video content so a title,
# description or transcript cannot close its block and pose as instructions.
DATA_TAG_CLOSE = re.compile(r"</\s*(metadata|chapters|reader_focus|transcript)\s*>", re.IGNORECASE)


def hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fill(meta: dict, segments: list[dict], focus: str) -> str:
    chapters = meta.get("chapters") or []
    duration = meta.get("duration_string") or (hms(meta["duration"]) if meta.get("duration") else "unknown")
    values = {
        "title": meta.get("title") or "unknown",
        "channel": meta.get("channel") or meta.get("uploader") or "unknown",
        "duration": duration,
        "url": meta.get("webpage_url") or "unknown",
        "description": meta.get("description") or "none",
        "chapters": "\n".join(f"[{hms(c['start_time'])}] {c.get('title', '')}" for c in chapters) or "none",
        "focus": focus,
        "transcript": "\n".join(f"[{hms(s['start'])}] {s['text'].strip()}" for s in segments),
    }
    values = {key: DATA_TAG_CLOSE.sub(r"&lt;/\1&gt;", value) for key, value in values.items()}

    template = (Path(__file__).parent / "prompt.md").read_text()
    prompt = template.split("\n---\n", 1)[1].lstrip()
    # Single pass: placeholder-like text inside video content is never substituted.
    return PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), prompt)


def main() -> None:
    meta_path, transcript_path, focus = sys.argv[1], sys.argv[2], sys.argv[3]
    meta = json.loads(Path(meta_path).read_text())
    segments = json.loads(Path(transcript_path).read_text())["segments"]
    print(fill(meta, segments, focus))


if __name__ == "__main__":
    main()
