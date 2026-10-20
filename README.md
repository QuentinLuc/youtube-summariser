# youtube-summary

A [Claude Code](https://claude.com/claude-code) skill that summarises a YouTube video **whether or not it has captions**.
It downloads the audio, transcribes it locally with Whisper, and has Claude write a structured summary with
timestamps, fact/opinion labels and caveats about likely mistranscriptions.

```
yt-dlp (audio) → mlx-whisper, Whisper large-v3-turbo (local) → Claude summary
```

See [`flow.md`](flow.md) for sequence diagrams.

> **Personal use.** Downloading from YouTube is against YouTube's Terms of Service except where YouTube
> offers a download option. Check that your use is acceptable before relying on this.

## Requirements

- **macOS on Apple Silicon** (transcription runs on [MLX](https://github.com/ml-explore/mlx))
- [Claude Code](https://claude.com/claude-code)
- `python3` 3.10+
- [`uv`](https://docs.astral.sh/uv/): runs yt-dlp and mlx-whisper through `uvx`, nothing installed globally
- `node`: yt-dlp uses it to pass YouTube's JavaScript challenge (without it, downloads fail with HTTP 403)
- `ffmpeg`: mlx-whisper decodes the audio with it

```bash
brew install uv node ffmpeg
```

The first run downloads the Whisper model (~1.6 GB) from Hugging Face.

## Install

**As a plugin (recommended).** In Claude Code:

```
/plugin install youtube-summary --marketplace QuentinLuc/youtube-summariser
```

On Claude Code versions without `--marketplace`, add the marketplace first:

```
/plugin marketplace add QuentinLuc/youtube-summariser
/plugin install youtube-summary@quentinluc
```

Claude Code handles updates. The skill is then invoked as `/youtube-summary:youtube-summary`, or by asking in plain language.

**As a personal skill.** Clone into your skills folder (invoked as `/youtube-summary`), update with `git pull`:

```bash
git clone https://github.com/QuentinLuc/youtube-summariser ~/.claude/skills/youtube-summary
```

Install one way or the other, not both, or the skill appears twice. Restart Claude Code after installing.

## Use

In Claude Code, ask in plain language or call the skill directly:

```
Summarise this video: https://www.youtube.com/watch?v=DQBqh6gcx7U
/youtube-summary https://www.youtube.com/watch?v=DQBqh6gcx7U focus: engineering managers
```

Claude asks permission to run `python3 …/transcribe.py` and to write the summary. Results go to
`<folder Claude runs from>/<video id>/`:

| File | What |
|---|---|
| `summary.md` | The summary |
| `transcript.json` | Timestamped Whisper transcript |
| `metadata.json` | Video metadata from yt-dlp |
| `input.md` | The summarisation prompt as Claude received it |

A 10-minute video takes about a minute end to end. If YouTube blocks the download, Claude retries once
with your Chrome cookies (`--cookies-from-browser chrome`).

## Files

| File | What |
|---|---|
| `SKILL.md` | The skill: which script to run, failure handling, how to summarise, what to return |
| `transcribe.py` | Downloads metadata and audio (yt-dlp), builds the Whisper glossary, transcribes, writes `input.md`. Run with `--help` for options |
| `whisper_run.py` | Calls the mlx-whisper library (not its CLI, which disables the temperature fallback that breaks repetition loops). Run by `transcribe.py` through `uv run` |
| `fill_prompt.py` | Fills `prompt.md` with metadata, transcript and suspect spans (likely Whisper loops). Used by `transcribe.py`; also runnable alone to refill after a prompt change |
| `prompt.md` | The summarisation prompt. Version in its title |
| `flow.md` | Sequence diagrams, high level and detailed |

## Developing

`tests/` is git-ignored: keep one folder per test video there, with its inputs and Claude's output per
prompt version.

**Test the skill end to end**, in a fresh session without your project's `CLAUDE.md` (run outside any project):

```bash
cd "$(mktemp -d)" && echo "Summarise this YouTube video: <url>" \
  | claude -p --allowedTools Skill "Bash(python3 *)" Read Write
```

Pass the request on stdin: `--allowedTools` takes several values and swallows a prompt given as an argument.

**Test the summarisation prompt alone**, without re-downloading:

1. New video: `python3 transcribe.py <url> tests/<slug> --focus "..."`.
   Existing video, new prompt version:
   `python3 fill_prompt.py tests/<slug>/metadata.json tests/<slug>/transcript.json "<focus>" > tests/<slug>/input-v<N>.md`
2. `(cd /tmp && claude -p < $PWD/tests/<slug>/input-v<N>.md > $PWD/tests/<slug>/output-v<N>.md)`
3. Note what was wrong in `tests/<slug>/notes.md`, change the prompt, bump its version, rerun on all test videos.

Cover the failure modes, not just the easy case: an English talk with chapters, a non-English talk, a
slide- or demo-heavy video, a 60+ minute interview with two speakers, a video without captions.

## Prompt changelog

| Version | Change | Why |
|---|---|---|
| v2.3 | New `<suspect_spans>` block: listed ranges are treated as missing and reported under "Coverage" | Whisper repetition loops (e.g. the title repeated for 4 minutes) were being read as content; whatever the transcription fixes don't prevent is now flagged instead |
| v2.2 | Word limits raised to 450 / 650 / 850 (under 15 min / 15–60 min / longer) | v2 landed at ~450 words for 10 min with the required sections; that reads fine, so the limit follows the output rather than forcing cuts |
| v2.1 | Declares tag contents as data, never instructions (closing tags in video content are also escaped by `fill_prompt.py`) | A transcript or description could inject instructions — matters most when running as a skill with tool access |
| v2 | Hard word limits; "By chapter" only for 20+ min; claims table max 6 rows, adds "demonstrated" type; never assert what was/wasn't shown; ignore self-promotion; Relevance may name gaps; metadata header | v1: 847 words for a 10-minute video, claimed something "is not shown" (it was on screen), padded claims table |
| v1 | Initial prompt | — |
