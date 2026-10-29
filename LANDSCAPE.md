# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing Python libraries in the "consume a podcast /
audio URL and hand off PCM or metadata" space, benchmarked against
`podcast-helper`. Ratings are ⭐ (1) to ⭐⭐⭐⭐⭐ (5), scored on
`podcast-helper`'s intended job: universal URL-in, PCM-out for AI
pipelines (files, direct enclosures, RSS / Atom feeds, yt-dlp-supported
sources), with signal-processing correctness and pragmatic ergonomics.
A library optimised for a very different job (e.g. offline podcast
management, general RSS reading, DAW-style audio editing) is not
penalised: the score just reflects fit to *this* niche.

## At a glance

<!-- TABLE:START -->
| Audio Ingestion | Universal URL-in | RSS / Atom parsing | yt-dlp resolution | Live-stream (HLS) | Correct resampling | PCM streaming | Compressed archive | Multi-surface |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **podcast-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| yt-dlp | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| streamlink | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| pytube | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| feedparser | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| podcastparser | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| ffmpeg-python | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| requests + ffmpeg (manual) | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| pydub | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ |
| librosa.load | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ |
| audioread | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/landscape.png)

The map is a 2-D summary of the eight criteria, so read it as a shape, not a scoreboard. `podcast-helper` is at the top-right corner. The axes read **Horizontal: Adaptable ↔ Efficient** and **Vertical: Precise ↔ Versatile**.
<!-- FIGURE:END -->

## Positioning

`podcast-helper` deliberately sits at the intersection of **yt-dlp-level
URL coverage** (any audio-bearing web URL, plus files, direct enclosures
and RSS feeds) and **AI-pipeline needs** (async PCM iterator with
Shannon-correct resampling, mono downmix or native channels preserved,
optional parallel compressed archive). It intentionally does *not* try
to compete with `podcastparser` / `feedparser` on the feed-parsing
frontier: it uses both, with `podcastparser` as primary and
`feedparser` as fallback for exotic Atom variants, and keeps
`yt-dlp` as an optional-yet-included integration for anything the
extension-based routing cannot classify.

The main differentiator against yt-dlp itself is the **async iterator
of PCM frames**, which lets a downstream ASR / VAD / diarisation
consumer pull frames at exactly the pace of the source (or as fast as
possible) without ever hitting the disk. The main differentiator against
`podcastparser` / `feedparser` is that a feed URL becomes an
audio-bearing URL transparently: the caller does not have to walk the
enclosure list themselves.

Resampling correctness is the quietest but most load-bearing edge:
`podcast-helper` resamples through ffmpeg's `swresample` / `soxr`, so a
downstream model always sees band-limited, aliasing-free PCM. A DIY
`requests + ffmpeg` chain can match that fidelity but leaves every other
concern (routing, feeds, streaming iterator, archive) to the caller.

## When to pick what

- **`podcast-helper`**: audio ingest for AI podcast pipelines, batch
  transcription, VAD tuning, dataset curation, ASR on live streams,
  Shannon-correct resampling with an optional compressed archive.
- **`yt-dlp`**: you only need the file on disk and do not care about
  RSS or async streaming.
- **`streamlink`**: you specifically need a live HLS stream pulled
  down and nothing else.
- **`feedparser` / `podcastparser`**: you only need to walk feed
  metadata; audio ingest is out of scope.
- **`pydub` / `librosa` / `audioread`**: you already have the file
  and want to manipulate or decode its samples with a mature audio
  library.
- **`ffmpeg-python` or plain `requests` + `ffmpeg`**: you want the
  decode and nothing else, and you are happy to own the URL routing,
  the feed walking and the framing yourself. That is the honest
  alternative to this package — `podcast-helper` is those three
  concerns plus an async iterator, not a better decoder.

## Sources and as-of date

Read on **2026-10-27**.

The `podcast-helper` row is scored against the code in this repository at
**v1.6.0**: `podcast_helper/streaming.py` for URL classification, the
ffmpeg command and the parallel archive; `podcast_helper/feed.py` for RSS
and Atom parsing (podcastparser first, feedparser as fallback); and the
five surfaces the README lists.

Four of the other rows were read from the versions actually installed in
this repository's environment on that date rather than from a changelog:
`yt-dlp 2026.6.9`, `feedparser 6.0.12`, `podcastparser 0.6.11` and
`ffmpeg-python 0.2.0`. Decoding behaviour was checked against
`ffmpeg 8.1.2`.

The remaining rows — `streamlink`, `pytube`, `pydub`, `librosa`,
`audioread` — are **not installed here**. They are scored from the scope
their own documentation claims, no version is attributed to them, and
nothing was benchmarked against them. The stars are a judgement of fit to
one niche, not a measurement; a disagreement is worth an issue, not a
correction to a number.

Two caveats belong with the table rather than under it:

- The five stars on "Correct resampling" are inherited from ffmpeg's
  `libswresample`, which does the actual work. The optional
  `resample_quality="high"` path needs an ffmpeg built with
  `--enable-libsoxr`, which a stock Homebrew build does not carry —
  measured here, where it yields zero frames.
- "Multi-surface" counts doors, not maturity: library, CLI, FastAPI HTTP,
  browser GUI and MCP all exist and are tested, but a single-purpose
  library scoring one star is not thereby worse at its own job.

## Ideas worth stealing

Researched rather than guessed: what each neighbour does better, and what this library would have to change to match it. Nothing here is a commitment — it is the reading list the next version starts from.

- **The Podcast 2.0 namespace — chapters, transcripts, funding, soundbites** — `feedparser` reads RSS and the iTunes namespace; the Podcast 2.0 namespace is where chapters and published transcripts live, and a transcript already in the feed is work this suite otherwise does again with a GPU.

- **`podcastparser` — a streaming parser sized for feeds** — It parses incrementally and is built for podcast feeds specifically, where `feedparser` builds the whole document. For a large feed read only to find the latest episode, that is the cheaper shape.

- **`streamlink` — a live episode is not a file** — Same lesson the Rust twin already encodes: resolve to an address for media that has no end, rather than trying to download it.

- **OPML — subscriptions are a list, and the list has a format** — Importing and exporting OPML is how every podcast client moves a subscription set. A library that resolves feeds one at a time is one function away from handling the set.
