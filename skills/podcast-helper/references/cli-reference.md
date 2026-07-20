# podcast-helper CLI reference

Two CLIs ship the same five subcommands with identical flag names:

- **argparse** `podcast-helper <sub> …` — always installed, zero extra deps.
- **click** `podcast-helper-click <sub> …` — install `podcast-helper[cli]`;
  same flags, nicer `--help`, shell completion.

Every subcommand is a thin dispatch onto the library functions, so the CLI never
diverges from `import podcast_helper as ph`.

## `feed` — dump an RSS / Atom feed as JSON

```bash
podcast-helper feed --url <FEED_URL> [--max-episodes N]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--url` (required) | — | RSS / Atom feed URL. |
| `--max-episodes` | all | Cap the number of episodes returned. |

Output: a JSON array of `Episode` dicts (see schema below), most-recent first.

## `latest` — the most recent episode

```bash
podcast-helper latest --url <FEED_URL> [--json]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--url` (required) | — | RSS / Atom feed URL. |
| `--json` | off | Print the full `Episode` dict; default prints only the enclosure URL. |

Output: the enclosure URL (one line) or the full `Episode` JSON with `--json`.

## `stream` — decode any URL to PCM (stdout) or an archive (disk)

```bash
podcast-helper stream --url <URL> [--output out.wav] [--sample-rate 16000] \
    [--mono | --stereo] [--frame-ms 20] [--speed 1.0] [--realtime | --no-realtime]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--url` (required) | — | Any audio-bearing URL (file / direct / feed / yt-dlp). |
| `--output` | none | If set, write a compressed archive (extension picks codec). Without it, raw f32le PCM goes to stdout. |
| `--sample-rate` | 16000 | Target sample rate in Hz (anti-aliasing low-pass at new Nyquist). |
| `--mono` / `--stereo` | mono | Downmix to one channel, or preserve native channel count. |
| `--frame-ms` | 20 | Frame duration in ms (20 matches Silero VAD). |
| `--speed` | 1.0 | Playback rate, VOD only, pitch-preserving. Raises on live. |
| `--realtime` / `--no-realtime` | realtime | Pace at wall-clock (`ffmpeg -re`) or decode as fast as possible. |

Raw PCM to a player: `podcast-helper stream --url ep.mp3 --no-realtime | \
ffplay -f f32le -ar 16000 -ac 1 -i -`

## `record` — archive any URL to a compressed file

```bash
podcast-helper record --url <URL> --output ep.mp3 [--sample-rate 16000] \
    [--mono | --stereo] [--frame-ms 20] [--speed 1.0]
```

Same streaming flags as `stream`; `--output` is **required**. Codec is picked
from the extension: `.mp3` (libmp3lame 128k), `.m4a`/`.aac` (aac 128k), `.opus`
(libopus 96k), `.ogg` (libvorbis q5), `.flac` (lossless), `.wav` (pcm_s16le).
Unknown extensions raise `ValueError`.

## `probe` — how is this URL classified?

```bash
podcast-helper probe --url <URL> [--show-url]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--url` (required) | — | URL to classify. |
| `--show-url` | off | Include the resolved direct URL (may carry signed tokens). |

Output JSON: `{"source_kind", "is_live", "header_count"[, "direct_url"]}`.
`source_kind` is one of `file`, `direct_audio`, `rss`, or `ytdlp:<extractor>`.

## `Episode` schema (returned by `feed` / `latest`)

```
{guid, title, description, link, published_at (ISO 8601 UTC),
 duration_seconds (int), enclosure_url, enclosure_type (MIME),
 enclosure_size_bytes (int), image_url}
```

`enclosure_url` is the direct audio URL — feed it straight to
`extract_audio_stream` / `stream` / `record`.

## Output contract

- `feed` / `latest --json` / `probe` → JSON on stdout (pipe to `jq`).
- `latest` (no `--json`) → a single URL on stdout.
- `stream` (no `--output`) → raw f32le PCM bytes on stdout.
- `stream --output` / `record` → the archive path on stdout (stream prints it to
  stderr; record to stdout); the deliverable is the file on disk.
- Library errors propagate as non-zero exit codes.
