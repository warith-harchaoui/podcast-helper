# podcast-helper CLI reference

One CLI over five verbs: `podcast-helper`, which ships with the core package —
no extra to install. `-h` / `--help` on any verb, `-V` for the version.

## `feed` — list a feed's episodes

```bash
podcast-helper feed FEED_URL [--limit N] [--json]
```

Returns `Episode` records: title, publication date, duration, and the
enclosure URL that `stream` / `record` consume. Use `--json` whenever the
output will be parsed.

## `latest` — the newest episode

```bash
podcast-helper latest FEED_URL [--json]
```

One call instead of "parse the feed, then sort by date". Prints the episode
and its enclosure URL.

## `probe` — what kind of URL is this

```bash
podcast-helper probe URL [--json]
```

Classifies the source — RSS/Atom feed, direct media file, HLS manifest,
yt-dlp-reachable page, or a local file — and reports whether it is **live**.
Run it first whenever the URL is unfamiliar: the answer decides whether you
need `feed` at all, and whether the stream will ever end.

## `stream` — decode to PCM

```bash
podcast-helper stream URL [--sample-rate HZ] [--channels N] [-o OUT.wav]
```

Decodes to raw PCM on stdout, or to a WAV with `-o`. `--sample-rate 16000
--channels 1` is the suite's speech convention and what most ASR front-ends
want. Pointed at a feed URL, it resolves the latest episode itself.

Without `-o` this is a pipe: another process consumes the samples and decides
when to stop. On a live source it never ends on its own.

## `record` — archive to a compressed file

```bash
podcast-helper record URL -o OUT.mp3        # also .m4a .opus .flac .wav
```

Writes the episode to disk in the format implied by the extension. On a live
source it keeps recording until interrupted — say so before starting one.

## Accepted URL kinds

- **RSS / Atom feeds** — `.xml`, `.rss`, `.atom`, and the usual hosts
  (`feeds.*`, anchor.fm, libsyn, buzzsprout, transistor.fm, simplecast,
  megaphone, acast, captivate, podbean). The latest episode's enclosure is
  picked automatically.
- **Direct audio** — `.mp3 .m4a .aac .opus .ogg .oga .wav .flac`, plus HLS
  `.m3u8` manifests.
- **yt-dlp sources** — YouTube, Vimeo, SoundCloud, Twitch VOD and live, and
  the rest of the extractor list (resolved via `bestaudio*`).
- **Local files** and `file://` — opened verbatim by ffmpeg.

Two known blocks, both with a documented way round: **Spotify** audio is
DRM-gated and raises with a hint, and **Apple Podcasts** links point at the
catalogue rather than the media. Find the show's RSS feed in both cases.

## Output contract

- `feed` / `latest` / `probe` print a human-readable summary, or JSON with
  `--json`.
- `record` prints the path it wrote; `stream -o` prints the WAV path, and bare
  `stream` writes samples to stdout and nothing else.
- Failures are logged through `os_helper` and exit non-zero; a partial
  recording is removed rather than left behind.
