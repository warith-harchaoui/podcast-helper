# Podcast Helper

[🇫🇷](LISEZMOI.md) · [🇬🇧](README.md)

[![CI](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Podcast Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

Consommateur universel de flux audio pour podcasts et toute URL portant de l'audio. **URL en entrée → PCM en sortie** pour les fichiers locaux, les URLs audio directes (enclosure RSS MP3 / M4A / Opus / WAV / HLS m3u8), les URLs de flux RSS / Atom (sélectionne automatiquement le dernier épisode), et toute source supportée par `yt-dlp` (YouTube, Vimeo, SoundCloud, Twitch VOD / live, …). Refuse d'emblée les URLs Spotify (DRM) et Apple Podcasts (catalogue), avec des indications claires sur le contournement via flux RSS.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Pourquoi cette bibliothèque

Les pipelines audio de podcasts (ASR, diarisation, résumé, indexation) commencent souvent par la même question : *« donne-moi un flux de frames PCM depuis cette URL, peu importe que ce soit un lien `.mp3`, un flux RSS, une vidéo YouTube, ou un podcast hébergé sur un CDN que je ne connais pas »*. Cette bibliothèque est cette fonction unique — plus les petits utilitaires autour (`feed`, `latest_episode`) qui rendent l'usage des sources RSS agréable.

# Installation

**Prérequis** — **Python 3.10–3.13** et **git**, **ffmpeg**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

Puis installer le paquet :


Il vous faut `ffmpeg` dans le PATH :

- macOS 🍎 : `brew install ffmpeg`

  (installez `brew` grâce à [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : récupérer un build sur [ffmpeg.org/download.html](https://ffmpeg.org/download.html) et l'ajouter au `PATH`.

Puis :

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/podcast-helper.git@v0.3.3
```

Cela tire [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) v1.2.0 (et transitivement `yt-dlp`, [os-helper](https://github.com/warith-harchaoui/os-helper), [audio-helper](https://github.com/warith-harchaoui/audio-helper), [video-helper](https://github.com/warith-harchaoui/video-helper)) plus [feedparser](https://feedparser.readthedocs.io/) + [podcastparser](https://podcastparser.readthedocs.io/) pour le RSS.

# Démarrage rapide

```python
import asyncio
import podcast_helper as ph

async def main():
    # Passez *n'importe quelle* URL — fichier, mp3 direct, flux RSS, YouTube, SoundCloud, Twitch VOD.
    async for frame in ph.extract_audio_stream(
        "https://feeds.npr.org/510289/podcast.xml",   # ← RSS, sélectionne le dernier épisode
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
    ):
        # frame["pcm"] : np.float32 (320,) pour 20ms @ 16kHz
        # frame["t_abs_s"] : 0.0, 0.02, 0.04, ...
        await asr.feed(frame["pcm"])

asyncio.run(main())
```

Pour le catalogue complet d'exemples (RSS, sources yt-dlp, flux live, stéréo / multicanal, anti-aliasing, pipelines ASR / VAD / résumé downstream), voir [📋 EXAMPLES.md](EXAMPLES.md).

# URLs acceptées

| Source | Détection | Ce qui se passe |
|---|---|---|
| **Fichier local** / `file://` | chemin existant sur disque OU schéma `file://` | ffmpeg l'ouvre directement. |
| **URL audio directe** (`.mp3`, `.m4a`, `.opus`, `.wav`, `.m3u8`, …) | l'extension de l'URL est un conteneur audio connu | ffmpeg l'ouvre directement avec vos éventuels `headers=`. |
| **Flux RSS / Atom** (`.xml`, `.rss`, `.atom`) | l'extension de l'URL est un conteneur de flux connu | `podcastparser` (repli : `feedparser`) le parse ; l'enclosure du dernier épisode est récupérée. |
| **YouTube / Vimeo / SoundCloud / Twitch VOD / Twitch live / …** | l'extracteur yt-dlp l'identifie | yt-dlp choisit `bestaudio*`, passe l'URL directe + les headers à ffmpeg. |
| **URL web générique** (tout le reste) | extracteur `generic` de yt-dlp | URL utilisée telle quelle. |
| **Spotify** (open.spotify.com) | match par hostname | `NotImplementedError` — l'audio Spotify est sous DRM. Utilisez le flux RSS de l'émission s'il existe. |
| **Apple Podcasts** (podcasts.apple.com) | match par hostname | `NotImplementedError` — les URLs Apple pointent vers le catalogue, pas vers l'audio. Utilisez le flux RSS de l'émission (lié sur son site, ou via `getrssfeed.com` / Podcast Index). |

# Correction du traitement du signal

Quand `target_sample_rate` diffère du taux source, la conversion est effectuée par `libswresample` (par défaut) ou `libsoxr` (`resample_quality="high"`). Les deux appliquent un **filtre passe-bas anti-repliement à la nouvelle fréquence de Nyquist** (`target_sample_rate / 2`) avant décimation — satisfaisant le théorème d'échantillonnage de Shannon-Nyquist. Aucun sous-échantillonnage naïf n'est utilisé.

La gestion des canaux a exactement deux modes — pas d'upmix synthétique :

| `to_mono` | Forme de sortie | Ce que fait ffmpeg |
|---|---|---|
| `True` (défaut) | `(n_samples,)` | Downmix standard (stéréo → L+R à -3 dB, 5.1 → mix ITU) |
| `False` | `(n_samples, n_channels)` entrelacé | Préserve le nombre natif de canaux de la source |

# Travailler explicitement avec les flux RSS

Si vous voulez inspecter ou choisir les épisodes vous-même :

```python
import podcast_helper as ph

# Liste complète des épisodes, du plus récent au plus ancien
episodes = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=20)
for ep in episodes:
    print(ep["published_at"], "—", ep["title"], "—", ep["duration_seconds"], "s")

# Ou juste le dernier
ep = ph.latest_episode("https://feeds.npr.org/510289/podcast.xml")
print(ep["title"], "→", ep["enclosure_url"])

# Puis streamer son audio
import asyncio
async def main():
    async for frame in ph.extract_audio_stream(ep["enclosure_url"]):
        ...
asyncio.run(main())
```

Chaque dictionnaire `Episode` a un schéma normalisé indépendamment de la variante du flux :

```
{guid, title, description, link, published_at (ISO UTC),
 duration_seconds, enclosure_url, enclosure_type, enclosure_size_bytes,
 image_url}
```

# Exposition multi-surface

`podcast-helper` expose les mêmes fonctions publiques via quatre
surfaces interchangeables — choisissez celle qui convient à l'appelant.

| Surface | Point d'entrée | Extra | Idéal pour |
|---|---|---|---|
| Bibliothèque (itérateur async) | `import podcast_helper as ph` | — | code Python, notebooks, ASR / VAD / résumé en aval |
| CLI argparse | `podcast-helper` | — (stdlib uniquement) | scripts shell, CI, pipelines ffmpeg |
| CLI click | `podcast-helper-click` | `[cli]` | shells click-native (auto-complétion bash / zsh, aide colorée) |
| API FastAPI | `uvicorn podcast_helper.api:app` | `[api]` | microservices HTTP, appelants multi-langages |
| Serveur MCP | `podcast-helper-mcp` | `[api,mcp]` | Claude Desktop, agents MCP, intégrations IDE |

Installez la combinaison d'extras qui vous convient :

```bash
pip install 'podcast-helper[cli]'          # + le jumeau click
pip install 'podcast-helper[api]'          # + la surface HTTP FastAPI
pip install 'podcast-helper[api,mcp]'      # + les outils MCP sur FastAPI
pip install 'podcast-helper[cli,api,mcp]'  # tout
```

Chaque surface publie les mêmes verbes — `feed`, `latest`, `stream`,
`record`, `probe` — avec des noms d'arguments identiques, donc
basculer d'une surface à l'autre relève du copier-coller. Le
Dockerfile de ce dépôt embarque les surfaces FastAPI + MCP sur le
port 8000 par défaut (`docker build -t podcast-helper . && docker run
--rm -p 8000:8000 podcast-helper`).

Pour un produit visuel ambitieux au-dessus, voir [`GUI.md`](GUI.md).
Pour une comparaison face à l'écosystème audio / podcast Python, voir
[`LANDSCAPE.md`](LANDSCAPE.md).

# Flux en direct

Pour les URLs live YouTube / Twitch, l'URL directe résolue est typiquement un manifeste HLS `.m3u8`. `extract_audio_stream` le détecte (`is_live=True`) et désactive automatiquement le pacing temps réel `-re` (la source impose son propre tempo). L'itérateur asynchrone tourne indéfiniment jusqu'à la fin du live ; à l'appelant de `break` quand il a fini.

`speed != 1.0` sur un flux live lève `ValueError` (depuis v0.2.0) — impossible d'aller plus vite que le bord du direct. Utilisez `speed=...` uniquement en VOD.

# Roadmap

| Version | Fonctionnalité |
|---|---|
| v0.1.x | `extract_audio_stream` + `feed` + `latest_episode`. yt-dlp + ffmpeg + feedparser + podcastparser. |
| **v0.2.0** (cette release) | `record_to="ep.mp3" \| ".m4a" \| ".opus" \| ".ogg" \| ".flac" \| ".wav"` (multi-output ffmpeg : PCM vers l'appelant + archive compressée sur disque en parallèle). `speed: float` pour la VOD (lève sur live), via le filtre `atempo=` (préserve la hauteur). |
| **v0.3.0** | `start_instant` / `end_instant` pour le seek VOD. `apple_podcasts_to_rss(url)` via l'API iTunes Search. Intégration Podcast Index. |
| **v0.3.0** | `apple_podcasts_to_rss(url)` via l'API iTunes Search. Intégration Podcast Index. La capture micro déménage dans `capture-helper`. |
| **v0.4.0+** | Chapitres (ID3 CTOC/CHAP, Podcasting 2.0 `<podcast:chapters>`), transcripts, import/export OPML. |

# Auteur
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Remerciements
Remerciements chaleureux à [Mohamed Chelali](https://mchelali.github.io) et [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) pour nos échanges fructueux.
