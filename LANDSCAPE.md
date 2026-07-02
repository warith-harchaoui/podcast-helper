# LANDSCAPE

Related and competing Python libraries in the "consume a podcast /
audio URL and hand off PCM or metadata" space, benchmarked against
`podcast-helper`. Ratings are `⭐️` (1) to `⭐️⭐️⭐️⭐️⭐️` (5), scored on
`podcast-helper`'s intended job — universal URL-in → PCM-out for AI
pipelines (files, direct enclosures, RSS / Atom feeds, yt-dlp-supported
sources), with signal-processing correctness and pragmatic ergonomics.
A library optimised for a very different job (e.g. offline podcast
management, general RSS reading, DAW-style audio editing) is not
penalised — the score just reflects fit to *this* niche.

## At a glance

| Library / project | Universal URL-in (file, direct, RSS, yt-dlp) | RSS / Atom feed parsing | yt-dlp source resolution | Live-stream (HLS) support | Shannon-correct resampling | PCM streaming (async iterator) | Parallel compressed archive | Multi-surface (CLI / API / MCP) |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **podcast-helper** *(this project)* | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ (ffmpeg swresample / soxr) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ (mp3 / m4a / opus / ogg / flac / wav) | ⭐️⭐️⭐️⭐️⭐️ (argparse + click + FastAPI + MCP) |
| yt-dlp (CLI) | ⭐️⭐️⭐️⭐️ (needs `--audio-format` post-processing) | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️ (via ffmpeg post-processor) | ⭐️ (writes to disk, not iterator) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️ (CLI only) |
| feedparser | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ (library only) |
| podcastparser | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ (iTunes + Podcasting 2.0) | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ (library only) |
| pyPodcastParser | ⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ |
| gPodder core | ⭐️⭐️ (download to disk) | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ (`.mp3` archive) | ⭐️⭐️ (desktop app) |
| Podcast Index client libs (`podcastindex-python`, `pypodcastindex`) | ⭐️ (discovery only) | ⭐️⭐️⭐️⭐️ (via Podcast Index API) | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️ |
| pydub | ⭐️⭐️ (file-only) | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️ (ffmpeg-backed) | ⭐️ (in-memory `AudioSegment`) | ⭐️⭐️⭐️⭐️ (export any format) | ⭐️⭐️ (library only) |
| librosa | ⭐️⭐️ (file / audioread) | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ (`resampy`) | ⭐️ (batch load) | ⭐️ | ⭐️ |
| soundfile | ⭐️ (WAV / FLAC / OGG only) | ⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️ (block reader) | ⭐️⭐️ | ⭐️ |
| requests + ffmpeg (DIY) | ⭐️⭐️ (only what you write) | ⭐️ | ⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ (whatever ffmpeg does) | ⭐️⭐️⭐️ (with subprocess) | ⭐️⭐️⭐️ | ⭐️ |

## Positioning

`podcast-helper` deliberately sits at the intersection of **yt-dlp-level
URL coverage** (any audio-bearing web URL, plus files, direct enclosures
and RSS feeds) and **AI-pipeline needs** (async PCM iterator with
Shannon-correct resampling, mono downmix or native channels preserved,
optional parallel compressed archive). It intentionally does *not* try
to compete with `podcastparser` / `feedparser` on the feed-parsing
frontier — it uses both, with `podcastparser` as primary and
`feedparser` as fallback for exotic Atom variants — and keeps
`yt-dlp` as an optional-yet-included integration for anything the
extension-based routing cannot classify.

The main differentiator against yt-dlp itself is the **async iterator
of PCM frames**, which lets a downstream ASR / VAD / diarisation
consumer pull frames at exactly the pace of the source (or as fast as
possible) without ever hitting the disk. The main differentiator against
`podcastparser` / `feedparser` is that a feed URL becomes an
audio-bearing URL transparently — the caller does not have to walk the
enclosure list themselves.

## When to pick what

- **`podcast-helper`** — audio ingest for AI podcast pipelines: batch
  transcription, VAD tuning, dataset curation, ASR on live streams,
  Shannon-correct resampling with an optional compressed archive.
- **`yt-dlp`** — you only need the file on disk and do not care about
  RSS or async streaming.
- **`feedparser` / `podcastparser`** — you only need to walk feed
  metadata; audio ingest is out of scope.
- **`gPodder`** — you want a desktop podcast client with a
  subscription store.
- **`pydub` / `librosa` / `soundfile`** — you already have the file
  and want to manipulate its samples with a mature audio library.
