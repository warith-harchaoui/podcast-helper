# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing Python libraries in the "consume a podcast /
audio URL and hand off PCM or metadata" space, benchmarked against
`podcast-helper`. Ratings are ⭐ (1) to ⭐⭐⭐⭐⭐ (5), scored on
`podcast-helper`'s intended job — universal URL-in → PCM-out for AI
pipelines (files, direct enclosures, RSS / Atom feeds, yt-dlp-supported
sources), with signal-processing correctness and pragmatic ergonomics.
A library optimised for a very different job (e.g. offline podcast
management, general RSS reading, DAW-style audio editing) is not
penalised — the score just reflects fit to *this* niche.

## At a glance

<!-- TABLE:START -->
| Audio Ingestion | Universal URL-in | RSS / Atom parsing | yt-dlp resolution | Live-stream (HLS) | Correct resampling | PCM streaming | Compressed archive | Multi-surface |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **podcast-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| yt-dlp | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| feedparser | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| podcastparser | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| pyPodcastParser | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| gPodder core | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| podcastindex-python | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| pydub | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| librosa | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ |
| soundfile | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐ |
| requests + ffmpeg | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/landscape.png)

The map is a 2-D summary of the eight criteria, so read it as a shape, not a scoreboard. `podcast-helper` is at the top-right corner. The axes read **Horizontal — Feed Expertise ↔ Streaming Versatility** and **Vertical — Compression Precision ↔ Multi-Format Mastery**.
<!-- FIGURE:END -->

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

Resampling correctness is the quietest but most load-bearing edge:
`podcast-helper` resamples through ffmpeg's `swresample` / `soxr`, so a
downstream model always sees band-limited, aliasing-free PCM. A DIY
`requests + ffmpeg` chain can match that fidelity but leaves every other
concern (routing, feeds, streaming iterator, archive) to the caller.

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
