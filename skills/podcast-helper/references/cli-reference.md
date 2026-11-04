# podcast-helper CLI reference

One CLI over five verbs: `podcast-helper`, which ships with the core package —
no extra to install. `-h` / `--help` on any verb, `-V` / `--version` for the
version. Every verb takes its source through the same `--url` option: there is
no positional URL.

## `feed` — list a feed's episodes

```bash
podcast-helper feed --url FEED_URL [--max-episodes N]
```

Prints the episodes as a JSON array of `Episode` records, most recent first:
`guid`, `title`, `description`, `link`, `published_at` (ISO UTC),
`duration_seconds`, `enclosure_url`, `enclosure_type`, `enclosure_size_bytes`,
`image_url`. The output is always JSON. A negative `--max-episodes` is refused
before the feed is fetched.

## `latest` — the newest episode

```bash
podcast-helper latest --url FEED_URL [--json]
```

Prints only the newest episode's enclosure URL, ready to pipe; `--json` prints
the whole `Episode` record instead.

## `probe` — what kind of URL is this

```bash
podcast-helper probe --url URL [--show-url]
```

Prints JSON: `source_kind` (`file`, `direct_audio`, or `ytdlp:<extractor>`),
`is_live` and `header_count`. A feed URL is resolved to its latest episode
first, so it reports that episode's kind. `--show-url` adds the resolved
`direct_url`, which may carry signed tokens. Run it first whenever the URL is
unfamiliar: it tells you whether the stream will ever end.

## `stream` — decode to PCM

```bash
podcast-helper stream --url URL [--sample-rate 16000] [--mono|--stereo] \
    [--frame-ms 20] [--speed 1.0] [--realtime|--no-realtime] [--output OUT.mp3]
```

Writes raw little-endian `float32` PCM to stdout (`ffplay -f f32le -ar 16000
-ac 1 -` plays it). `--mono` (the default) downmixes; `--stereo` keeps the
source's native channel count, interleaved. `--realtime` (the default) paces
decoding at wall-clock, `--no-realtime` decodes as fast as possible. `--speed`
changes the rate without changing pitch, on VOD only: a live source refuses
it. With `--output`, the PCM is discarded and a compressed archive is written
instead, its path echoed on stderr. Pointed at a feed URL, it resolves the
latest episode itself.

Without `--output` this is a pipe: another process consumes the samples and
decides when to stop. On a live source it never ends on its own.

## `record` — archive to a compressed file

```bash
podcast-helper record --url URL --output OUT.mp3   # also .m4a .aac .opus .ogg .flac .wav
```

Takes the same `--sample-rate`, `--mono/--stereo`, `--frame-ms` and `--speed`
as `stream`, never paces at wall-clock, and prints the path it wrote. The codec
follows the extension; any other extension is refused. On a live source it
keeps recording until interrupted — say so before starting one.

## Accepted URL kinds

- **RSS / Atom feeds** — recognised by a `.xml`, `.rss` or `.atom` extension,
  or, when yt-dlp cannot resolve an extension-less URL, by an RSS/Atom/XML
  `Content-Type`. The latest episode's enclosure is picked automatically.
- **Direct audio** — `.mp3 .m4a .aac .opus .ogg .oga .wav .flac` and a few
  more containers, plus HLS `.m3u8` manifests (treated as live).
- **yt-dlp sources** — YouTube, Vimeo, SoundCloud, Twitch VOD and live, and
  the rest of the extractor list (resolved via `bestaudio*`).
- **Local files** and `file://` — opened verbatim by ffmpeg.

Two known blocks, both with a documented way round: **Spotify** audio is
DRM-gated and raises with a hint, and **Apple Podcasts** links point at the
catalogue rather than the media. Find the show's RSS feed in both cases.

## Output contract

- `feed`, `probe` and `latest --json` print JSON; bare `latest` prints one URL.
- `record` prints the path it wrote; `stream --output` prints it on stderr, and
  bare `stream` writes samples to stdout and nothing else.
- Any failure (an unreachable URL, an ffmpeg error, a fired read timeout)
  prints one `Error: …` line on stderr and exits 1. A partial archive is left
  where it was written.
