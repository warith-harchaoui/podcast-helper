# podcast-helper skill — exhaustive trigger catalogue

Auditable superset of the `description:` TRIGGER clause in `SKILL.md` (the
description is what a host model sees before loading; this file is the
human-reviewable full list). Keep the two in sync, and mirror the repo-root
`TRIGGERS.md`.

## Fire (positive triggers)

**Feed / episode listing**
- "list the episodes in this RSS / Atom feed", "what episodes does this podcast have"
- "get the latest episode of this show", "what's the newest episode"
- "what's the enclosure / direct audio URL of the latest episode"
- "resolve the RSS feed for this podcast", "read this podcast feed"
- "how long is the latest episode", "when was it published"

**PCM streaming (URL-in → PCM-out)**
- "give me a PCM stream from this podcast / episode / URL"
- "decode this audio URL to raw PCM / f32le / 16 kHz / mono"
- "stream this episode into my ASR / VAD / transcription / diarization pipeline"
- "I need audio frames from this feed / YouTube / SoundCloud / Twitch URL"
- "pull the audio off this live stream", "consume this HLS m3u8 as PCM"

**Archiving / recording**
- "download / archive / record this episode to mp3 / m4a / opus / ogg / flac / wav"
- "save the latest episode as an mp3", "grab this podcast episode as a file"
- "archive this live stream while it airs"

**Classification / probing**
- "classify / probe this URL", "what kind of URL is this"
- "is this a feed, a direct file, or a yt-dlp source", "is this URL live"
- "how will podcast-helper resolve this URL"

**Explicit command / function mentions**
- `podcast-helper`, `podcast-helper-click`, `podcast-helper-mcp`
- subcommands `feed latest stream record probe`
- functions `extract_audio_stream feed latest_episode`; types `Episode PcmFrame`

**Surfaces**
- "run the podcast API / podcast-helper server", "expose these as HTTP / MCP tools"
- "open the podcast GUI / episode browser"
- "how do I install / run podcast-helper"

**URL / host cues** (with a feed-or-audio intent)
- feed extensions: `.xml .rss .atom`; hosts: `feeds.*`, `anchor.fm`, `libsyn`,
  `buzzsprout`, `transistor.fm`, `simplecast`, `megaphone`, `acast`,
  `captivate`, `podbean`, `redcircle`, `spreaker`
- direct audio: `.mp3 .m4a .aac .opus .ogg .oga .wav .flac .m3u8`
- yt-dlp sources: YouTube, Vimeo, SoundCloud, Twitch VOD / live, and the long
  yt-dlp extractor list

## Do NOT fire (SKIP)

- **Transcription / captions / subtitles / speech-to-text / diarization** →
  vocal-helper / a whisper skill. podcast-helper produces PCM; it does not read
  words out of audio.
- **Text-to-speech / voice cloning / synthesis / music generation** → not this skill.
- **File-to-file editing of a LOCAL audio file already in hand** — convert,
  trim, split, concat, silence, room-tone, stem separation, MFCC similarity →
  **audio-helper**. podcast-helper is URL-oriented ingest, not a file editor.
- **Downloading a VIDEO file or video frames from a URL** → youtube-helper /
  video-helper.
- **DAW-style mixing / mastering / loudness normalization (LUFS)** → not this skill.
- **Spotify audio** — DRM-gated; podcast-helper raises with a hint. Don't retry;
  find the show's RSS feed.

## Enforcement checklist

A trigger is "enforced" when (1) it is represented in `SKILL.md`'s `description`
TRIGGER clause so the host sees it pre-load; (2) the SKIP clause is present so
the skill does not over-fire (especially the audio-helper / vocal-helper /
youtube-helper boundaries); (3) this catalogue lists the positive and negative
buckets so a human can audit coverage against the description.
