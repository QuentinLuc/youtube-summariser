# YouTube summariser — POC

> **Graduated to a skill on 2026-10-20:** `~/.claude/skills/youtube-summary/` (`SKILL.md` = `skill-prompt.md`,
> plus copies of `transcribe.py`, `fill_prompt.py`, `prompt.md`). The skill is now the source of truth;
> this folder keeps the test bench and history. Copy changes across if you iterate here.

Goal: summarise a YouTube video without relying on YouTube's captions
(yt-dlp → ffmpeg → mlx-whisper → Claude). This folder holds the summarisation
prompt while we iterate on it. It becomes a skill once the prompt is stable.

## Files

| File | What |
|---|---|
| `skill-prompt.md` | The orchestration prompt (future `SKILL.md`): run `transcribe.py`, handle failures, follow the filled `input.md`, write `summary.md`. |
| `transcribe.py` | Steps 1–3: yt-dlp metadata + native audio, mlx-whisper transcript (it decodes the audio with ffmpeg), then fills the prompt. `python3 transcribe.py <url> tests/<slug> --focus "..."` writes `metadata.json`, `transcript.json`, `input.md`. Needs uv, node and ffmpeg. |
| `fill_prompt.py` | Refills the prompt from an existing metadata + transcript, e.g. after a prompt change. |
| `prompt.md` | The summarisation prompt (step 4 of the pipeline). Current version in its title. |
| `tests/` | One folder per test video: inputs used and Claude's output, per prompt version. |

## How to test end to end (skill prompt)

From outside the project folder, so no project CLAUDE.md is loaded. Run from this folder:

```bash
P=$PWD
cd /tmp && { sed '1,/^---$/d' $P/skill-prompt.md; printf '\nURL: <youtube url>\nFocus: general\nSkill directory: %s\n' "$P"; } \
  | claude -p --model claude-opus-5-5 --add-dir $P --allowedTools "Bash(python3 *)" Read Write
```

Pass the prompt on stdin: `--allowedTools` takes several values and swallows a prompt given as an argument.
Output lands in `<folder Claude runs from>/<video id>/` (`summary.md` plus the intermediate files),
here `/tmp/<video id>/`. To keep a test in this folder, add `Output directory: $P/tests/<video id>`.

## How to test the summarisation prompt alone

1. New video: `python3 transcribe.py <url> tests/<slug> --focus "..."`.
   Existing video, new prompt version: `python3 fill_prompt.py tests/<slug>/metadata.json tests/<slug>/transcript.json "<focus>" > tests/<slug>/input-v<N>.md`.
2. Give the filled prompt to a fresh Claude session: `claude -p < tests/<slug>/input-v<N>.md > tests/<slug>/output-v<N>.md`
   (run it from outside this folder so no project CLAUDE.md is loaded).
3. Save the output as `tests/<video-slug>/output-v<N>.md` and note what was wrong.
4. Change the prompt, bump the version, rerun on all test videos.

## Test set (suggested)

Cover the failure modes, not just the easy case:

- A talk in English with chapters (baseline)
- A talk in French (checks English output and term correction)
- A video heavy on slides or demos (checks visual-only caveats)
- A long interview, 60+ min, with two speakers (checks attribution and length)

## Changelog

| Version | Change | Why |
|---|---|---|
| v1 | Initial prompt | — |
| v2.2 | Word limits raised to 450 / 650 / 850 (under 15 min / 15–60 min / longer) | v2 landed at ~450 words for 10 min with the required sections; that reads fine, so the limit follows the output rather than forcing cuts (review S9) |
| v2.1 | Declares tag contents as data, never instructions (closing tags in video content are also escaped by `fill_prompt.py`) | Code review: a transcript or description could inject instructions — matters most once this runs as a skill with tool access |
| v2 | Hard word limits; "By chapter" only for 20+ min; claims table max 6 rows, adds "demonstrated" type; never assert what was/wasn't shown; ignore self-promotion; Relevance may name gaps; metadata header | v1 on `vibe-coding-playwright-qa`: 847 words for 10 min, claimed the prompt "is not shown" (it was pasted on screen), padded claims table |
