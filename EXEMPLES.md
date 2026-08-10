# Exemples Podcast Helper

Recettes pratiques pour transformer un flux audio de podcast en trames PCM.
Tous les extraits supposent :

```python
import asyncio
import podcast_helper as ph
import os_helper as osh

osh.verbosity(2)   # pour que les appels osh.info(...) s'affichent sur stdout
```

et que `ffmpeg` est sur le PATH (`brew install ffmpeg` sur macOS : installez
d'abord `brew` via [brew.sh](https://brew.sh/) ; `sudo apt install ffmpeg`
sur Linux).

---

## Table des matières

1. [Installation](#installation)
2. [URL → PCM en un seul appel](#url--pcm-en-un-seul-appel)
3. [Flux RSS : dernier épisode, liste, par index](#flux-rss--dernier-épisode-liste-par-index)
4. [Audio YouTube / Vimeo / SoundCloud](#audio-youtube--vimeo--soundcloud)
5. [Flux en direct](#flux-en-direct)
6. [Sources stéréo / multicanal](#sources-stéréo--multicanal)
7. [Anti-repliement : rééchantillonneur haute précision](#anti-repliement--rééchantillonneur-haute-précision)
8. [Pipelines en aval courants](#pipelines-en-aval-courants)

---

## Installation

```bash
pip install --force-reinstall --no-cache-dir \
  podcast-helper
```

Entraîne avec lui `youtube-helper` (et par transitivité `yt-dlp`,
`audio-helper`, `video-helper`, `os-helper`), ainsi que `feedparser` et
`podcastparser`.

## URL → PCM en un seul appel

`extract_audio_stream(url, ...)` est en général la seule fonction dont vous
ayez besoin : elle détermine le type d'URL reçu (fichier local, audio
direct, flux RSS, source yt-dlp) et produit des trames PCM.

```python
async def main():
    async for frame in ph.extract_audio_stream(
        "https://feeds.npr.org/510289/podcast.xml",
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
    ):
        # frame["pcm"] : np.float32, forme (320,) pour 20 ms @ 16 kHz
        # frame["t_abs_s"] : 0.00, 0.02, 0.04, ...
        await asr.feed(frame["pcm"])

asyncio.run(main())
```

Le même code fonctionne avec :

```python
# Fichier local
ph.extract_audio_stream("/Users/me/podcasts/episode.mp3")

# Enclosure RSS directe
ph.extract_audio_stream("https://cdn.simplecast.com/audio/.../episode.mp3")

# Vidéo YouTube : yt-dlp résout la meilleure piste audio
ph.extract_audio_stream("https://www.youtube.com/watch?v=YE7VzlLtp-4")

# SoundCloud
ph.extract_audio_stream("https://soundcloud.com/user/track-id")
```

## Flux RSS : dernier épisode, liste, par index

```python
# Juste le dernier épisode en date
ep = ph.latest_episode("https://feeds.npr.org/510289/podcast.xml")
print(ep["title"], "→", ep["enclosure_url"])
# Up First → https://chrt.fm/track/.../media.mp3

# Parcourir le catalogue (du plus récent au plus ancien)
episodes = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=20)
for ep in episodes:
    print(ep["published_at"], "—", ep["title"], f"({ep['duration_seconds']}s)")
    # 2026-06-29T07:00:00+00:00 — Friday's Headlines (730s)
    # 2026-06-28T07:00:00+00:00 — Thursday's Headlines (708s)
    # ...

# Choisir par index (l'épisode d'hier = deuxième plus récent)
ep = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=2)[1]

# Puis diffuser son audio
async def stream_one():
    async for frame in ph.extract_audio_stream(ep["enclosure_url"]):
        ...
asyncio.run(stream_one())
```

Chaque `Episode` est un dictionnaire typé :

| Champ | Type | Remarques |
|---|---|---|
| `guid` | str | Identifiant stable de l'épisode (vide si le flux n'en fournit pas). |
| `title` | str | |
| `description` | str | Peut contenir du balisage HTML issu des notes de l'épisode. |
| `link` | str | Page web de l'épisode (pas l'URL audio). |
| `published_at` | str | ISO 8601 UTC `YYYY-MM-DDTHH:MM:SS+00:00` (vide si absent). |
| `duration_seconds` | int | 0 si absent. |
| `enclosure_url` | str | L'URL audio réelle : à passer à `extract_audio_stream`. |
| `enclosure_type` | str | Type MIME (`"audio/mpeg"`, `"audio/x-m4a"`, …). |
| `enclosure_size_bytes` | int | 0 si absent. |
| `image_url` | str | Illustration de l'épisode, repli sur celle de l'émission. |

## Audio YouTube / Vimeo / SoundCloud

Toute URL que `yt-dlp` sait extraire fonctionne directement. Pour un
contenu soumis à vérification d'âge ou réservé aux abonnés, passez
`cookies_from_browser` :

```python
async def youtube_premium():
    async for frame in ph.extract_audio_stream(
        "https://www.youtube.com/watch?v=...",
        cookies_from_browser="firefox",   # ou "chrome" / "safari"
        target_sample_rate=16000,
    ):
        ...
```

## Flux en direct

Pour les URL de direct YouTube / Twitch, `extract_audio_stream` détecte le
drapeau live et désactive le rythme temps réel `-re` (la source impose déjà
son propre rythme). L'itérateur asynchrone tourne jusqu'à la fin du direct
ou jusqu'à ce que le client se coupe.

```python
async def transcribe_live(url):
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000):
        if vad.is_speech(frame["pcm"]):
            transcript = asr.feed(frame["pcm"])
            if "stop" in transcript:
                break
```

Dans une prochaine version, `speed != 1.0` sur un flux en direct lèvera
`ValueError` : on ne peut pas avancer plus vite que le direct lui-même.

## Sources stéréo / multicanal

Par défaut, `to_mono=True` réduit la source à un canal unique (matrice de
mixage standard de ffmpeg). Pour conserver le nombre de canaux natif de la
source, passez `to_mono=False`. Le tableau `pcm` de la trame prend alors la
forme `(n_samples, n_channels)`, entrelacée par échantillon :

```python
async def keep_stereo():
    async for frame in ph.extract_audio_stream(
        "https://cdn.example.com/album.flac",
        to_mono=False,
        target_sample_rate=44100,
    ):
        # frame["pcm"] : np.float32, forme (882, 2) pour 20 ms @ 44,1 kHz stéréo
        left, right = frame["pcm"][:, 0], frame["pcm"][:, 1]
        ...
```

Il n'existe pas de réglage `channels=N` : le mixage vers le mono est le
comportement canonique et déterministe ; un suréchantillonnage arbitraire
relève d'un choix créatif qui appartient à votre pipeline en aval.

## Anti-repliement : rééchantillonneur haute précision

Quand `target_sample_rate` diffère du débit de la source, la conversion
passe par défaut par `libswresample` de ffmpeg : un rééchantillonneur
polyphasé avec filtre passe-bas anti-repliement calé sur la nouvelle
fréquence de Nyquist (`target_sample_rate / 2`). C'est correct au sens de
Shannon, largement suffisant pour la reconnaissance vocale, la détection
d'activité vocale ou le machine learning.

Pour un travail audiophile ou sans perte, activez `libsoxr` en précision
28 bits (environ 10 fois plus lent, artefacts inaudibles) :

```python
ph.extract_audio_stream(
    url,
    target_sample_rate=44100,
    resample_quality="high",   # utilise aresample=...:resampler=soxr:precision=28
)
```

## Pipelines en aval courants

### Reconnaissance vocale (Silero, Whisper-streaming, etc.)

```python
async def transcribe(url):
    chunks = []
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000, frame_ms=20):
        chunks.append(frame["pcm"])
        if len(chunks) * 0.02 >= 5.0:           # toutes les 5 secondes
            audio = np.concatenate(chunks)
            print(whisper.transcribe(audio))
            # "And in tonight's headlines, the Senate voted..."
            chunks.clear()
```

### Ingestion filtrée par détection d'activité vocale

```python
import torch
vad = torch.jit.load("silero_vad.jit")

async def vad_ingest(url):
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000, frame_ms=20):
        if vad(torch.from_numpy(frame["pcm"])) > 0.5:
            await queue.put(frame)
```

### Résumé en flux (fenêtres adaptées à un LLM)

```python
async def summarise_window(url, window_s=60.0):
    chunks, total = [], 0.0
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000):
        chunks.append(frame["pcm"])
        total += 0.02
        if total >= window_s:
            audio = np.concatenate(chunks)
            transcript = whisper.transcribe(audio)
            summary = llm.summarise(transcript)
            yield summary
            chunks, total = [], 0.0
```
