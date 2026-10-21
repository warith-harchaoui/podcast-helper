# Podcast Helper

[🇫🇷](https://github.com/warith-harchaoui/podcast-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/podcast-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/podcast-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#la-promesse)

`Podcast Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

## La promesse

**Local d'abord, par conception.** podcast-helper s'exécute entièrement sur votre machine : il ne récupère que les épisodes et les flux que vous demandez et les traite localement. Vos données ne partent jamais vers un service tiers, il n'y a aucune télémétrie, aucun compte, aucun verrouillage propriétaire dans le cloud. Fait partie de la suite [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) : la souveraineté sur vos données grâce à l'open source local d'abord.

Consommateur universel de flux audio, pour les podcasts et toute URL porteuse d'audio. **URL en entrée, PCM en sortie** (le PCM, ou modulation par impulsions codées, est le flux brut d'échantillons audio non compressés qu'attendent les modèles de reconnaissance vocale et d'analyse audio, à la différence d'un fichier compressé comme un MP3), pour les fichiers locaux, les URL audio directes (enclosure RSS MP3, M4A, Opus, WAV, HLS m3u8), les URL de flux RSS/Atom (le dernier épisode est sélectionné automatiquement) et toute source prise en charge par `yt-dlp` (YouTube, Vimeo, SoundCloud, Twitch VOD ou live et bien d'autres). Les URL Spotify (verrouillées par DRM) et Apple Podcasts (catalogue) sont refusées d'emblée, avec une indication claire pour contourner via le flux RSS.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/logo.png)](https://deraison.ai/ai-helpers)

## Documentation

[💻 Documentation](https://deraison.ai/ai-helpers/docs/podcast-helper-doc/)

[🗺️ Paysage](https://github.com/warith-harchaoui/podcast-helper/blob/main/PAYSAGE.md)

[📋 Exemples](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXEMPLES.md)

## Éprouvé en production

`podcast-helper` est publié sur [PyPI](https://pypi.org/project/podcast-helper/) avec des tags versionnés selon le versionnage sémantique (actuellement v1.1.5), ce qui fait qu'une plage figée comme `podcast-helper>=1.1.0,<2` reste stable dans le temps. L'intégration continue (CI, une chaîne automatisée qui fait tourner les tests et le linter à chaque push) est au vert sur `main` : `pytest` puis `ruff check` doivent tous deux passer avant qu'une contribution soit intégrée. La bibliothèque dépend de deux sœurs de la même suite AI Helpers, [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) pour la résolution via yt-dlp et [os-helper](https://github.com/warith-harchaoui/os-helper) pour la journalisation et les utilitaires de fichiers partagés. Elle est elle-même une dépendance de [vocal-helper](https://github.com/warith-harchaoui/vocal-helper) (transcription avec étiquetage des locuteurs), qui construit son ingestion audio, en direct comme hors ligne, directement sur `extract_audio_stream`.

## Pourquoi cette bibliothèque

Les pipelines audio de podcasts commencent souvent par la même demande, que l'étape suivante soit la reconnaissance vocale automatique (_Automatic Speech Recognition_ ou ASR), la diarisation (étiqueter qui parle et quand), la détection d'activité vocale (_Voice Activity Detection_ ou VAD, repérer les passages où il y a effectivement de la parole avant de lancer dessus les modèles plus lourds), le résumé ou l'indexation : *« donne-moi un flux de frames PCM depuis cette URL, que ce soit un lien `.mp3`, un flux RSS, une vidéo YouTube ou un podcast hébergé sur un CDN inconnu »*. Cette bibliothèque, c'est cette fonction-là, plus les petits utilitaires autour (`feed`, `latest_episode`) qui rendent les sources RSS agréables à manipuler.

## Installation

**Prérequis :** **Python 3.10-3.13**, **git** et **ffmpeg**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

On recommande de travailler dans un environnement Python. Si vous ne savez pas en créer un, voir [🥸 Conseils techniques](https://deraison.ai/4ml/#install).

### Depuis PyPI (recommandé)

```bash
# Bibliothèque de base
pip install podcast-helper

# Surfaces optionnelles
pip install "podcast-helper[cli]"
pip install "podcast-helper[api]"
pip install "podcast-helper[mcp]"
```

Ceci tire [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) (et transitivement `yt-dlp`, [os-helper](https://github.com/warith-harchaoui/os-helper), [audio-helper](https://github.com/warith-harchaoui/audio-helper), [video-helper](https://github.com/warith-harchaoui/video-helper)), ainsi que [feedparser](https://feedparser.readthedocs.io/) et [podcastparser](https://podcastparser.readthedocs.io/) pour le RSS.

### Depuis les sources (sans PyPI)

```bash
git clone https://github.com/warith-harchaoui/podcast-helper.git
cd podcast-helper
pip install -e .

# Surfaces optionnelles
pip install -e ".[cli]"
pip install -e ".[api]"
pip install -e ".[mcp]"
```

## Démarrage rapide

```python
import asyncio
import podcast_helper as ph


async def main():
    # Passez *n'importe quelle* URL : fichier, mp3 direct, flux RSS, YouTube, SoundCloud, Twitch VOD.
    async for frame in ph.extract_audio_stream(
        "https://feeds.npr.org/510289/podcast.xml",  # ← RSS, sélectionne le dernier épisode
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
    ):
        # frame["pcm"] : np.float32 (320,) pour 20ms @ 16kHz
        # frame["t_abs_s"] : 0.0, 0.02, 0.04, ...
        await asr.feed(frame["pcm"])


asyncio.run(main())
```

Pour le catalogue complet d'exemples (RSS, sources yt-dlp, flux live, stéréo / multicanal, anti-aliasing, pipelines ASR / VAD / résumé downstream), voir [📋 EXAMPLES.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXAMPLES.md).

## URLs acceptées

| Source | Détection | Ce qui se passe |
|---|---|---|
| **Fichier local** / `file://` | chemin existant sur disque OU schéma `file://` | ffmpeg l'ouvre directement. |
| **URL audio directe** (`.mp3`, `.m4a`, `.opus`, `.wav`, `.m3u8`, …) | l'extension de l'URL est un conteneur audio connu | ffmpeg l'ouvre directement avec vos éventuels `headers=`. |
| **Flux RSS / Atom** (`.xml`, `.rss`, `.atom`) | l'extension de l'URL est un conteneur de flux connu | `podcastparser` (repli : `feedparser`) le parse ; l'enclosure du dernier épisode est récupérée. |
| **YouTube / Vimeo / SoundCloud / Twitch VOD / Twitch live / …** | l'extracteur yt-dlp l'identifie | yt-dlp choisit `bestaudio*`, passe l'URL directe + les headers à ffmpeg. |
| **URL web générique** (tout le reste) | extracteur `generic` de yt-dlp | URL utilisée telle quelle. |
| **Spotify** (open.spotify.com) | match par hostname | `NotImplementedError` : l'audio Spotify est verrouillé par DRM. Utilisez le flux RSS de l'émission s'il existe. |
| **Apple Podcasts** (podcasts.apple.com) | match par hostname | `NotImplementedError` : les URL Apple pointent vers le catalogue, pas vers l'audio. Utilisez le flux RSS de l'émission (lié sur son site ou via `getrssfeed.com` / Podcast Index). |

## Correction du traitement du signal

Quand `target_sample_rate` diffère du taux source, la conversion est effectuée par `libswresample` (par défaut) ou `libsoxr` (`resample_quality="high"`). Les deux appliquent un **filtre passe-bas anti-repliement à la nouvelle fréquence de Nyquist** (`target_sample_rate / 2`, le plafond que le théorème d'échantillonnage fixe pour la fréquence la plus haute qu'un taux donné peut représenter) avant décimation : tout contenu au-dessus de ce plafond est retiré en premier, car sinon il se replierait vers le bas dans la plage audible sous forme de bruit parasite une fois le taux abaissé, un artefact appelé repliement. Le sous-échantillonnage naïf, qui se contente d'écarter des échantillons sans ce filtre, saute cette étape et laisse passer le repliement ; il n'est jamais utilisé ici.

La gestion des canaux a exactement deux modes, sans upmix synthétique :

| `to_mono` | Forme de sortie | Ce que fait ffmpeg |
|---|---|---|
| `True` (défaut) | `(n_samples,)` | Downmix standard (stéréo → L+R à -3 dB, 5.1 → mix ITU) |
| `False` | `(n_samples, n_channels)` entrelacé | Préserve le nombre natif de canaux de la source |

## Travailler explicitement avec les flux RSS

Si vous voulez inspecter ou choisir les épisodes vous-même :

```python
import podcast_helper as ph

# Liste complète des épisodes, du plus récent au plus ancien
episodes = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=20)
for ep in episodes:
    print(ep["published_at"], "|", ep["title"], "|", ep["duration_seconds"], "s")

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

## Exposition multi-surface

`podcast-helper` expose les mêmes fonctions publiques via cinq
surfaces interchangeables ; choisissez celle qui convient à l'appelant.

| Surface | Point d'entrée | Extra | Idéal pour |
|---|---|---|---|
| Bibliothèque (itérateur async) | `import podcast_helper as ph` | aucun | code Python, notebooks, ASR / VAD / résumé en aval |
| CLI argparse | `podcast-helper` | aucun (stdlib uniquement) | scripts shell, CI, pipelines ffmpeg |
| CLI click | `podcast-helper-click` | `[cli]` | shells click-native (auto-complétion bash / zsh, aide colorée) |
| API FastAPI | `uvicorn podcast_helper.api:app` | `[api]` | microservices HTTP, appelants multi-langages |
| GUI navigateur | `GET /gui` (servi par l'API) | `[api]` | explorateur d'épisodes glisser-une-URL : lister · prévisualiser · archiver, sans terminal |
| MCP | `podcast-helper-mcp` | `[mcp]` | tout hôte agentique compatible MCP (appelle les mêmes points d'accès comme outils) |

Installez la combinaison d'extras qui vous convient :

```bash
pip install 'podcast-helper[cli]'          # + le jumeau click
pip install 'podcast-helper[api]'          # + la surface HTTP FastAPI
pip install 'podcast-helper[mcp]'          # + les outils MCP (inclut [api] automatiquement)
pip install 'podcast-helper[cli,api,mcp]'  # tout
```

Chaque surface publie les mêmes verbes, `feed`, `latest`, `stream`,
`record`, `probe`, avec des noms d'arguments identiques, donc
basculer d'une surface à l'autre relève du copier-coller. Le
Dockerfile de ce dépôt embarque la surface FastAPI sur le
port 8000 par défaut (`docker build -t podcast-helper . && docker run
--rm -p 8000:8000 podcast-helper`).

### GUI navigateur : l'explorateur d'épisodes (`GET /gui`)

Avec l'extra `[api]`, l'application FastAPI sert un **explorateur
d'épisodes** en une seule page, autonome (Tailwind via CDN + JS
vanilla, sans étape de build) qui pilote exactement les mêmes points
de terminaison :

```bash
pip install 'podcast-helper[api]'
uvicorn podcast_helper.api:app --port 8000
# ouvrez http://localhost:8000/gui  (ou simplement http://localhost:8000/)
```

Collez une URL de flux / RSS / audio / yt-dlp → **Lister les épisodes**
(appelle `/feed`) → cliquez sur un épisode pour voir ses métadonnées et
écouter l'enclosure en ligne → **Enregistrer dans un fichier** (appelle
`/record`) pour télécharger une archive compressée. **Probe** classe
n'importe quelle URL. Rien n'est téléversé : la lecture diffuse
l'enclosure directement dans votre navigateur ; l'archivage exécute
ffmpeg sur votre propre machine.

La page parle **français et anglais**. `GET /gui?lang=fr|en` choisit la langue,
un drapeau dans l'en-tête bascule de l'une à l'autre, et un code que le fichier
de locales ne porte pas retombe sur la langue par défaut au lieu d'échouer.
Toutes les chaînes vivent dans
[`podcast_helper/locales/i18n.yaml`](https://github.com/warith-harchaoui/podcast-helper/blob/main/podcast_helper/locales/i18n.yaml),
lu par `os_helper.Locales` — le chargeur partagé par la suite — si bien que
traduire la page n'oblige jamais à ouvrir un fichier Python.

Pour le catalogue exhaustif des déclencheurs, formulations, URLs
acceptées et des cas où *ne pas* utiliser podcast-helper, voir
[`TRIGGERS.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/TRIGGERS.md).

Pour un produit visuel ambitieux au-dessus, voir [`GUI.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/GUI.md).

### En tant que skill d'agent

`skills/podcast-helper/` empaquette podcast-helper comme **skill Claude** *et* skill
**OpenCode**, pour qu'un agent puisse s'en saisir à votre place. Voir
[`skills/README.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/skills/README.md) pour l'installer (liens
symboliques vers `~/.claude/skills/` et `~/.opencode/skills/`) et
[`TRIGGERS.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/TRIGGERS.md) pour le catalogue exhaustif des
déclencheurs — `scripts/check_triggers.py` maintient la description du skill
alignée dessus ; la suite de tests échoue si une capacité cesse d'être
nommée.

## Flux en direct

Pour les URLs live YouTube / Twitch, l'URL directe résolue est typiquement un manifeste HLS (_HTTP Live Streaming_, un protocole qui livre l'audio ou la vidéo sous forme d'une suite de petits fichiers segments listés dans une playlist `.m3u8`). `extract_audio_stream` le détecte (`is_live=True`) et désactive automatiquement le pacing temps réel `-re` (la source impose son propre tempo). L'itérateur asynchrone tourne indéfiniment jusqu'à la fin du live ; à l'appelant de `break` quand il a fini.

`speed != 1.0` sur un flux live lève `ValueError` : impossible d'aller plus vite que le bord du direct. Utilisez `speed=...` uniquement en VOD.

## Quand un flux se bloque

ffmpeg n'applique aucun délai d'E/S sans qu'on le lui demande : une connexion
que le serveur a à moitié fermée est donc attendue indéfiniment — ffmpeg reste
à 0 % de CPU sur une socket qui ne livrera plus un octet tandis que le
consommateur attend un tube qui ne se fermera jamais. Les sources réseau sont
donc lues avec `-rw_timeout` (60 s par défaut), pour qu'une connexion morte
lève une erreur au lieu de bloquer :

```bash
export PODCAST_HELPER_RW_TIMEOUT=120   # secondes ; 0 désactive la borne
```

Les fichiers locaux n'en reçoivent jamais : un chemin sur disque ne peut pas se
bloquer sur une socket.

**Cela borne la lecture, cela ne rend pas le blocage impossible.** Une exécution
a été observée bloquée plus de quatre heures sur une URL `googlevideo.com` avec
`-rw_timeout 60000000` sur sa ligne de commande : l'option ne couvre pas toutes
les façons qu'a un CDN de se taire. Si votre traitement *doit* aboutir, donnez-lui
une borne qui lui appartient — un superviseur, un chien de garde — plutôt que de
vous reposer sur celle-ci.

## Pas encore construit

- `start_instant` / `end_instant` pour le seek VOD.
- `apple_podcasts_to_rss(url)`, qui résoudrait une URL de catalogue Apple Podcasts vers son flux RSS via l'API iTunes Search.
- Intégration à l'API Podcast Index.
- Chapitres (ID3 CTOC/CHAP, Podcasting 2.0 `<podcast:chapters>`) et transcriptions.
- Import et export OPML.

Voir [CHANGELOG.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/CHANGELOG.md) pour ce qui a déjà été livré.

## Version Rust

Un crate compagnon, [`podcast-helper-rs`](https://github.com/warith-harchaoui/podcast-helper-rs),
réécrit la même promesse « une URL en entrée, du PCM en sortie » en Rust :
fichiers locaux, URLs audio directes, flux RSS/Atom décodés via `ffmpeg`,
avec YouTube/Vimeo/SoundCloud/Twitch délégués à `youtube-helper-rs`.
L'intérêt : un binaire statique unique, sans interpréteur Python à
installer, utile quand l'ingestion de podcasts doit s'intégrer à un
pipeline Rust plus large (par exemple pour alimenter un service Rust de
reconnaissance vocale ou de diarisation) plutôt qu'un pipeline Python.
C'est une surface v0.1 plus restreinte, pas un remplacement complet — pas
encore d'itérateur asynchrone par trame, pas d'extraction `itunes:duration` ;
voir son README pour les différences volontaires exactes.

## Auteur

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Remerciements

Remerciements chaleureux à [Mohamed Chelali](https://mchelali.github.io) et [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) pour nos échanges fructueux.

## Licence

Ce projet est sous licence BSD-3-Clause. Voir le fichier [LICENSE](https://github.com/warith-harchaoui/podcast-helper/blob/main/LICENSE) pour les détails.
