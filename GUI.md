# GUI — Podcast Helper

> A design plan, not a CLI mirror. The CLI already handles "one URL,
> one operation, one PCM stream". A GUI must go further — otherwise
> why build one? This document lays out an ambitious, opinionated
> visual product for the podcast-ingest-for-AI workflow.

## North star

> **A dashboard where a single URL becomes a live, auditable audio
> pipeline — feed → episodes → PCM frames → downstream — with every
> intermediate step visible, hearable, and A/B comparable.**

Podcast ingest for AI (ASR, diarisation, VAD tuning, embedding
generation, dataset curation) is inherently a *many-URL, many-episode,
many-model* problem. The CLI does one URL well; the GUI's job is to
make the **fleet-wide reality** — a subscription list, a catalog of
processed episodes, a queue of ffmpeg pulls in flight — legible and
interactive.

## Three surfaces, one product

### 1. Subscription Wall *(primary surface)*

- One tile per RSS feed the user has subscribed to. Tile shows: cover
  art, show title, host, episode count, "last published" freshness
  badge, and a mini-histogram of episode durations across the feed.
- Click a tile → drills into the **Episode Grid** for that feed.
- Add a feed by drop / paste (URL or OPML). Right-click a tile →
  "Refresh now" (re-hits the RSS URL). Bulk import → OPML picker.
- One-click **health check** per feed: green if RSS returns 2xx and
  ≥1 audio enclosure, amber if podcastparser fell back to feedparser
  (rare feed flavour), red if the feed 404s or has no audio items.

### 2. Episode Grid + Waveform Peek *(the actual work surface)*

- Contact-sheet layout: each episode as a card with title, publish
  date, duration, a **static waveform thumbnail** (pre-rendered from
  the enclosure), and quick actions (Play · Archive · Feed to ASR).
- Sortable / filterable columns (duration, date, enclosure size,
  transcribed y/n, ASR word count).
- **Peek waveform**: hover a card → expanded waveform + spectrogram
  in a side panel; scrub with the mouse → hear from that point. All
  handled by a local ``podcast_helper.api`` server the GUI already
  ships alongside — no cloud roundtrip.
- One card, three states: *raw enclosure*, *resampled 16 kHz mono*,
  *VAD-gated speech only*. Toggle to compare visually + audibly —
  this is the "diff view" moment the CLI cannot reproduce.

### 3. Live Broadcast Console

For live streams (Twitch, YouTube Live, HLS m3u8 feeds), the GUI
needs its own surface — a live stream is not an episode.

- A "Now on air" strip on top: one row per live URL the user is
  monitoring, with a scrolling waveform of the last 30 s and a
  live-VAD gauge (talk/silence ratio).
- Right-click a live row → **branch record**: start a background
  ffmpeg archive to a rolling `.m4a` while the live PCM keeps flowing
  to the console.
- Instant "chapter marker" hotkey: press ``M`` while listening to
  stamp the current absolute time — the CLI operator writes marker
  times to disk with a couple of Python lines; the GUI operator hits
  a key.

## Design principles

- **URL is the primitive.** Every workflow starts by dropping a URL.
  The GUI must classify (feed / direct enclosure / yt-dlp source /
  live) *before* the user picks an action, so options like "record",
  "list episodes" or "listen" surface only when applicable.
- **Time is a first-class citizen.** Playhead is a singleton across
  the app. Any two waveforms on screen (raw vs resampled, past
  episode vs new one, live vs archive) scrub together.
- **Server / client are the same binary.** The GUI is a thin JS
  client on top of the existing ``podcast_helper.api`` server — no
  hidden compute, no separate backend to maintain.
- **Explain the classification.** For any URL, the GUI shows *how*
  podcast-helper resolved it (source_kind, is_live, header count),
  so ambiguity is never buried in tooltips.
- **Keyboard first.** Space = play/pause; ``[``/``]`` = jump
  ±5 s; ``M`` = marker; ``A``/``B`` = swap between two waveforms in
  the diff view.
- **Colorblind-safe by construction.** All state uses shape + color +
  text, never color alone (see companion ``front-colors`` skill).

## What we deliberately don't do

- **No podcast player.** Overcast / Pocket Casts / Antennapod already
  exist for casual listening. This is a *pipeline dashboard*, not a
  consumption app.
- **No cloud lock-in.** Everything runs on the FastAPI server the
  container already ships (``podcast-helper[api]``).
- **No transcription in-app.** ASR belongs to a downstream helper
  (``ask-helper``, ``docs-helper``). This GUI produces the PCM
  frames and the archives; other tools consume them.

## Stack

- Front end: TypeScript + Svelte 5 + WaveSurfer.js (waveforms) +
  Vega-Lite (spectrograms). No React — matches the `front-ui`
  companion skill's stack.
- Back end: the FastAPI app already exists (``podcast_helper.api``).
  GUI is a client only.
- Persistence: subscription list + episode metadata cached in
  SQLite in the user's data dir. RSS refetches are HTTP-conditional
  (ETag / If-Modified-Since) so subscription walls of hundreds of
  feeds are cheap to keep fresh.

## Milestones

| Milestone | What ships | Why first |
| --- | --- | --- |
| M0 | Subscription Wall with 1 add-URL / OPML import. Feed health check. | Anchor the URL-first workflow. |
| M1 | Episode Grid with static waveform thumbnails + Peek waveform. | Where the value lands: seeing 200 episodes at a glance. |
| M2 | Diff view (raw vs 16 kHz mono vs VAD-gated). | The "we can only do this in a GUI" moment for signal auditing. |
| M3 | Live Broadcast Console + branch-record + marker hotkey. | Unlocks the live workflow (Twitch / YouTube Live). |
| M4 | Similarity clustering: drop 500 archived episodes, cluster by MFCC / speaker embedding, click a cluster to hear a representative. | Dataset triage at pipeline scale — the true "why a GUI" case. |

## Non-goals (recorded so we do not drift)

- Not a full podcast client.
- Not a hosted SaaS.
- Not a substitute for the CLI in CI (subscription lists export as
  OPML that CI can replay headless).

## Success metric

> A user who owns 200 subscriptions and needs to prep a training set
> for a speech model picks 50 relevant episodes across 20 feeds,
> archives them at 16 kHz mono, and hands the folder to their ASR
> pipeline — in one afternoon, in one window, without touching a
> terminal.

If we ship that, we win.
