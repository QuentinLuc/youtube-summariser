# Flow — `youtube-summary` skill (as implemented, 2026-10-20)

## High level: components only

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant C as Claude<br/>(youtube-summary skill)
    participant D as Downloader<br/>(yt-dlp)
    participant ST as Speech-to-text<br/>(Whisper, local)
    participant PB as Prompt builder<br/>(prompt.md + fill_prompt)

    U->>C: "Summarise <YouTube URL>" (+ optional focus)
    C->>D: URL
    D-->>PB: metadata (title, description, chapters)
    D->>ST: audio + language + glossary
    ST-->>PB: timestamped transcript
    PB-->>C: filled summarisation prompt (input.md)
    C->>C: summarise, following input.md
    C-->>U: summary (+ summary.md, transcript.json)
```

Steps 2–6 run inside one script call (`transcribe.py`); Claude is both the orchestrator and the summariser.

## Detailed: every tool and call

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant C as Claude<br/>(youtube-summary skill)
    participant T as transcribe.py
    participant Y as yt-dlp[default]<br/>(via uvx)
    participant N as node<br/>(JS challenge solver)
    participant YT as YouTube
    participant W as mlx-whisper<br/>(via uvx)
    participant F as ffmpeg
    participant HF as Hugging Face Hub
    participant FP as fill_prompt.fill()

    U->>C: "Summarise <url>" or /youtube-summary <url> [focus]
    C->>C: load SKILL.md, resolve output dir<br/>(default ./<video id>)
    C->>T: python3 <skill dir>/transcribe.py <url> <out dir> --focus "..."<br/>(Bash, 10 min timeout)

    Note over T,YT: 1/3 metadata
    T->>Y: --ignore-config --js-runtimes node --skip-download --dump-json -- <url>
    Y->>YT: GET watch page + player API
    YT-->>Y: JS challenge
    Y->>N: run solver script
    N-->>Y: solved challenge
    YT-->>Y: title, channel, description, chapters, language
    Y-->>T: JSON on stdout
    T->>T: write metadata.json<br/>language: "fr-FR" → "fr"<br/>glossary: title + channel + chapter titles

    Note over T,YT: 2/3 audio
    T->>Y: -f bestaudio -o <tempdir>/audio.%(ext)s -- <url>
    Y->>YT: GET audio stream (native format)
    alt HTTP 403 / bot check
        YT-->>Y: error
        Y-->>T: exit 1 + stderr
        T-->>C: "yt-dlp failed" + stderr
        C->>T: rerun once with --cookies-from-browser chrome
        Note over C,T: fails again → Claude reports the error and stops
    else success
        YT-->>Y: audio.webm / audio.m4a
        Y-->>T: file in temp dir (.part files ignored)
    end

    Note over T,HF: 3/3 transcription
    T->>W: mlx_whisper <audio> --model whisper-large-v3-turbo<br/>--language --initial-prompt <glossary> --output-format json
    W->>F: ffmpeg -i <audio> -ac 1 -ar 16000 -f s16le -
    F-->>W: raw 16 kHz mono PCM
    opt first run only
        W->>HF: download mlx-community/whisper-large-v3-turbo (~1.6 GB)
        HF-->>W: weights, cached in ~/.cache/huggingface
    end
    W->>W: run Whisper on MLX (Apple Silicon GPU), 30 s windows
    W-->>T: audio.json (timestamped segments)
    T->>T: move to transcript.json, delete temp dir (audio)

    T->>FP: fill(metadata, segments, focus)
    FP->>FP: read prompt.md, escape data-block closing tags,<br/>single-pass {{placeholder}} substitution
    FP-->>T: filled prompt
    T->>T: write input.md
    T-->>C: "done: N segments, language=…"

    Note over C: Summarise
    C->>C: read input.md, follow it<br/>(video content = data, never instructions)
    C->>C: write summary.md
    C-->>U: summary + paths of summary.md and transcript.json
```
