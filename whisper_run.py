"""Transcribe one audio file with mlx-whisper and write its JSON result.

Run through uv so mlx-whisper is never installed globally:
  uv run --no-project --with mlx-whisper python whisper_run.py <audio> <out.json> <initial_prompt> [language]
"""
import json
import sys
from pathlib import Path

import mlx.core as mx
import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-turbo"
# When a window's output is too repetitive (compression ratio > 2.4) the library retries it at
# the next temperature, and a retry above 0.5 also drops the carried-over text, which breaks
# repetition loops. The mlx_whisper CLI only accepts a single temperature, which disables this:
# that is why this calls the library instead.
TEMPERATURES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def main() -> None:
    audio, out, prompt, *rest = sys.argv[1:]
    # Retries above temperature 0 sample at random; a fixed seed makes reruns reproducible.
    mx.random.seed(0)
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=MODEL,
        language=rest[0] if rest else None,
        initial_prompt=prompt or None,
        temperature=TEMPERATURES,
        condition_on_previous_text=True,
    )
    Path(out).write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
