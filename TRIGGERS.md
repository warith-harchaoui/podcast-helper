# TRIGGERS — podcast-helper

This is the user-facing, exhaustive catalogue of what `podcast-helper` can do and
the natural-language phrasings, commands, functions, URLs, and file types that
should invoke it — whether you call it yourself or drive it as a Claude /
OpenCode **skill** (see [`skills/podcast-helper/SKILL.md`](skills/podcast-helper/SKILL.md)
and its [`references/triggers.md`](skills/podcast-helper/references/triggers.md)).

`podcast-helper` is **URL-in → PCM-out**: it resolves any podcast / RSS / audio /
video URL and hands you a stream of PCM frames, plus friendly RSS helpers. It is
local-first, ffmpeg + yt-dlp backed. It does **not** transcribe, synthesize, or
edit files already on disk.

## The five verbs → how to invoke

| Intent | CLI | Library | API / MCP |
|--------|-----|---------|-----------|
| List an RSS / Atom feed's episodes | `podcast-helper feed` | `feed` | `GET /feed` |
| Get the latest episode / enclosure URL | `podcast-helper latest` | `latest_episode` | `GET /latest` |
| Decode any URL to raw PCM (stdout / WAV) | `podcast-helper stream` | `extract_audio_stream` | `POST /stream` |
| Archive any URL to a compressed file | `podcast-helper record` | `extract_audio_stream(record_to=…)` | `POST /record` |
| Classify a URL (file/direct/rss/yt-dlp, live?) | `podcast-helper probe` | `_resolve_source` | `GET /probe` |

Every verb is also reachable through the click CLI (`podcast-helper-click …`,
same flags) and the browser episode browser at `GET /gui`.

## Natural-language phrasings that should fire

- **feed**: "list the episodes in this RSS feed", "what episodes does this
  podcast have", "read this podcast feed".
- **latest**: "get the latest episode of this show", "what's the enclosure URL
  of the newest episode".
- **stream**: "give me a PCM stream from this podcast / YouTube / SoundCloud
  URL", "decode this audio URL to 16 kHz mono", "stream this episode into my ASR
  / VAD / transcription pipeline", "consume this live HLS as PCM".
- **record**: "download / archive this episode to mp3 / m4a / opus / flac / wav",
  "save the latest episode as an mp3", "archive this live stream while it airs".
- **probe**: "classify / probe this URL", "is this a feed, a direct file, or a
  yt-dlp source", "is this URL live".
- **Surfaces**: "run the podcast API / MCP server", "open the episode browser
  GUI", "install podcast-helper".

## URLs and file types it accepts

- **RSS / Atom feeds**: `.xml .rss .atom`; hosts like `feeds.*`, `anchor.fm`,
  `libsyn`, `buzzsprout`, `transistor.fm`, `simplecast`, `megaphone`, `acast`,
  `captivate`, `podbean` (auto-picks the latest episode's enclosure).
- **Direct audio enclosures**: `.mp3 .m4a .aac .opus .ogg .oga .wav .flac`, and
  HLS `.m3u8` manifests.
- **yt-dlp sources**: YouTube, Vimeo, SoundCloud, Twitch VOD / live, and the
  long yt-dlp extractor list (resolved via `bestaudio*`).
- **Local files / `file://`**: opened verbatim by ffmpeg.

## When NOT to use podcast-helper (SKIP)

- Transcription / captions / subtitles / speech-to-text / diarization → use
  `vocal-helper` / a whisper skill. podcast-helper produces PCM, not words.
- Text-to-speech, voice cloning, synthesis, music generation.
- File-to-file editing of a **local** audio file already in hand (convert, trim,
  split, concat, silence, room-tone, stem separation, MFCC similarity) → use
  `audio-helper`.
- Downloading a **video** file or video frames from a URL → `youtube-helper` /
  `video-helper`.
- DAW-style mixing / mastering / loudness normalization.
- **Spotify** audio is DRM-gated; podcast-helper raises with a hint — find the
  show's RSS feed instead. **Apple Podcasts** (`podcasts.apple.com`) links point
  to the catalog, not the audio — use the show's RSS feed.

## See also

- [`README.md`](README.md) — features, install, quick start.
- [`EXAMPLES.md`](EXAMPLES.md) — runnable recipes.
- [`GUI.md`](GUI.md) — the shipped minimal GUI + the roadmap for a richer one.
- [`skills/README.md`](skills/README.md) — installing this as an agent skill.
