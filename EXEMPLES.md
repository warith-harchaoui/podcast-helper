# Exemples Podcast Helper

🇫🇷 Français · [🇬🇧 EXAMPLES.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXAMPLES.md)

Recettes exécutables pour transformer n'importe quelle URL porteuse d'audio
en PCM (modulation par impulsions codées : les échantillons audio bruts et
non compressés que consomment les modèles de parole et d'audio).

Les extraits qui n'ont besoin que de `ffmpeg` et d'un fichier local ont été
**exécutés** ; leur sortie est recopiée telle quelle ci-dessous. Ceux qui
exigent le réseau — un flux RSS en ligne, une URL YouTube — sont signalés
comme tels et ne portent aucune sortie, car en inventer une serait le moyen
le plus rapide de rendre ce fichier mensonger.

## Table des matières

1. [Mise en place](#mise-en-place)
2. [Une URL en entrée, des trames PCM en sortie](#1-une-url-en-entrée-des-trames-pcm-en-sortie)
3. [Les flux RSS et le dictionnaire Episode](#2-les-flux-rss-et-le-dictionnaire-episode)
4. [YouTube, SoundCloud et les autres sources yt-dlp](#3-youtube-soundcloud-et-les-autres-sources-yt-dlp)
5. [Flux en direct](#4-flux-en-direct)
6. [Stéréo et multicanal](#5-stéréo-et-multicanal)
7. [Le rééchantillonneur haute précision](#6-le-rééchantillonneur-haute-précision)
8. [Une archive compressée pendant le flux](#7-une-archive-compressée-pendant-le-flux)
9. [Alimenter un modèle en aval](#8-alimenter-un-modèle-en-aval)
10. [La suite qui travaille ensemble](#9-la-suite-qui-travaille-ensemble)
11. [Ligne de commande](#ligne-de-commande)
12. [Dépannage](#dépannage)

## Mise en place

```bash
pip install podcast-helper
```

Cette ligne installe la bibliothèque et la commande `podcast-helper`. Les
surfaces HTTP et MCP vivent derrière des extras (`[api]`, `[mcp]`) ; les
sections ci-dessous précisent quand vous en avez besoin.

`ffmpeg` doit être sur le `PATH` : c'est le décodeur, pas un accélérateur
facultatif.

```bash
brew install ffmpeg                 # macOS
sudo apt install -y ffmpeg          # Debian / Ubuntu
```

Tous les extraits qui suivent supposent ces imports :

```python
import asyncio
import logging

import numpy as np
import os_helper as osh
import podcast_helper as ph
```

Les exemples exécutés lisent tous la même tonalité stéréo de 440 Hz d'une
seconde, pour que vous puissiez les reproduire sans réseau :

```bash
ffmpeg -f lavfi -i "sine=frequency=440:duration=1:sample_rate=44100" -ac 2 tone.wav
```

## 1. Une URL en entrée, des trames PCM en sortie

`extract_audio_stream` est la seule fonction dont la plupart des appelants
ont besoin. Elle classe l'URL qu'on lui passe (fichier local, audio direct,
flux RSS, source yt-dlp) et produit des dictionnaires `PcmFrame` :
`t_abs_s` (secondes depuis le début de la source), `pcm` (échantillons
float32) et `voiced` (toujours `None` ici — c'est une détection d'activité
vocale en aval qui le renseigne).

```python
async def main():
    count = 0
    async for frame in ph.extract_audio_stream(
        "tone.wav",
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
        realtime=False,  # décoder aussi vite que la machine le permet
    ):
        if count < 3:
            rms = float(np.sqrt(np.mean(frame["pcm"] ** 2)))
            print(
                f"t={frame['t_abs_s']:.2f}s shape={frame['pcm'].shape} "
                f"dtype={frame['pcm'].dtype} rms={rms:.3f}"
            )
        count += 1
    print("frames:", count)


asyncio.run(main())
```

```text
t=0.00s shape=(320,) dtype=float32 rms=0.088
t=0.02s shape=(320,) dtype=float32 rms=0.088
t=0.04s shape=(320,) dtype=float32 rms=0.089
frames: 50
```

Cinquante trames de 320 échantillons : 20 ms à 16 kHz, soit une seconde
d'audio. Le même appel accepte tous les autres genres d'URL, sans drapeau :

```python
ph.extract_audio_stream("/Users/moi/podcasts/episode.mp3")  # fichier local
ph.extract_audio_stream("https://cdn.example.com/ep/042.mp3")  # enclosure directe
ph.extract_audio_stream("https://feeds.example.org/show.xml")  # RSS, dernier épisode
ph.extract_audio_stream("https://www.youtube.com/watch?v=YE7VzlLtp-4")  # source yt-dlp
```

`realtime` vaut `True` par défaut, ce qui cale le décodage sur l'horloge
murale (le `-re` de ffmpeg). Passez `realtime=False` pour du traitement par
lots ; lisez le [Dépannage](#dépannage) avant de sortir d'une boucle
`realtime=False` par un `break`.

## 2. Les flux RSS et le dictionnaire Episode

Quand vous voulez choisir l'épisode vous-même au lieu de laisser
`extract_audio_stream` prendre le plus récent, `feed` et `latest_episode`
exposent le flux directement. Les deux font une requête HTTP : cet extrait
**exige le réseau** et aucune sortie n'est recopiée.

```python
FEED = "https://feeds.npr.org/510289/podcast.xml"

episodes = ph.feed(FEED, max_episodes=20)  # du plus récent au plus ancien
for episode in episodes:
    print(episode["published_at"], "|", episode["title"], "|", episode["duration_seconds"], "s")

recent = ph.latest_episode(FEED)  # ignore les items sans enclosure
print(recent["title"], "->", recent["enclosure_url"])

hier = ph.feed(FEED, max_episodes=2)[1]  # choix par index


async def stream_one():
    async for frame in ph.extract_audio_stream(hier["enclosure_url"]):
        print(frame["t_abs_s"], frame["pcm"].shape)
        break


asyncio.run(stream_one())
```

`feed` trie du plus récent au plus ancien sur `published_at` et renvoie les
items sans date à la fin ; `max_episodes` plafonne le nombre d'épisodes (un
plafond négatif lève `ValueError` au lieu de découper par l'autre bout).
`latest_episode` renvoie le plus récent épisode qui porte réellement une
enclosure audio, ce qui explique pourquoi il ne s'écrit pas `feed(url)[0]` :
les bandes-annonces et les items purement textuels sont écartés.

Chaque épisode est un dictionnaire typé `Episode`, aux mêmes clés quelle que
soit la variante du flux :

| Clé | Type | Remarques |
|---|---|---|
| `guid` | str | Identifiant stable de l'épisode ; vide si le flux n'en fournit pas. |
| `title` | str | Titre de l'épisode. |
| `description` | str | Notes d'épisode ; peut contenir du HTML. |
| `link` | str | Page web de l'épisode, **pas** l'URL audio. |
| `published_at` | str | ISO 8601 UTC `YYYY-MM-DDTHH:MM:SS+00:00`, vide si absent. |
| `duration_seconds` | int | `0` quand le flux ne le dit pas. |
| `enclosure_url` | str | L'URL audio — c'est elle que vous streamez. |
| `enclosure_type` | str | Type MIME (`"audio/mpeg"`, `"audio/x-m4a"`, …). |
| `enclosure_size_bytes` | int | `0` si absent. |
| `image_url` | str | Illustration de l'épisode, à défaut celle de l'émission. |

`podcastparser` analyse le flux en premier ; `feedparser` sert de repli pour
les variantes Atom qu'il refuse. Vous n'avez jamais à choisir entre les deux.

## 3. YouTube, SoundCloud et les autres sources yt-dlp

Tout ce que yt-dlp sait extraire passe par le même argument `url` :
l'extracteur résout `bestaudio*` puis transmet l'URL directe et ses en-têtes
à ffmpeg. Pour un contenu soumis à vérification d'âge ou réservé aux
abonnés, empruntez les cookies d'un navigateur. **Exige le réseau**, donc
aucune sortie recopiée :

```python
async def gated():
    async for frame in ph.extract_audio_stream(
        "https://www.youtube.com/watch?v=YE7VzlLtp-4",
        cookies_from_browser="firefox",  # ou "chrome", "safari", ...
        target_sample_rate=16000,
    ):
        print(frame["t_abs_s"], frame["pcm"].shape)
        break


asyncio.run(gated())
```

`headers={...}` se superpose aux en-têtes propres à chaque source calculés
par yt-dlp, vos clés gagnant, pour les sources qui réclament un `Referer` ou
un jeton.

Spotify et Apple Podcasts sont refusés avant toute requête réseau : voir le
[Dépannage](#dépannage) pour le message exact et le contournement.

## 4. Flux en direct

Une URL de direct YouTube ou Twitch se résout en manifeste HLS.
`extract_audio_stream` le remarque (`is_live=True` côté résolveur) et coupe
de lui-même le cadencement `-re`, puisqu'une source en direct impose déjà
son rythme. L'itérateur tourne alors jusqu'à la fin de l'émission. **Exige
le réseau** :

```python
async def follow_live(url):
    seconds = 0.0
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000):
        seconds += frame["pcm"].size / 16000
        if seconds >= 30.0:
            print("30 s d'audio en direct récupérées")
            return  # lisez la note ci-dessous avant de sortir en avance


asyncio.run(follow_live("https://www.twitch.tv/une-chaine-en-direct"))
```

Deux contraintes sont ici réelles, pas stylistiques :

- `speed != 1.0` sur une source en direct lève `ValueError`. On ne peut pas
  dépasser le bord du direct ; ralentir laisserait le consommateur
  décrocher sans borne.
- Sortir en avance est la seule façon de quitter une source en direct ; il
  existe un défaut de nettoyage sur ce chemin qui mérite d'être connu. Il a
  été mesuré sur de la VOD décodée avec `realtime=False`, là où ffmpeg prend
  de l'avance et où le tube non lu s'accumule ; une source en direct livre à
  son propre rythme, donc l'accumulation qui déclenche le défaut ne se forme
  pas. Le [Dépannage](#dépannage) donne la reproduction.

## 5. Stéréo et multicanal

`to_mono=True` (le défaut) applique le downmix standard de ffmpeg et rend un
tableau 1-D. `to_mono=False` préserve le nombre de canaux natif de la source
et rend un tableau 2-D de forme `(n_samples, n_channels)` :

```python
async def keep_channels():
    first = True
    # Volontairement épuisé jusqu'au bout plutôt qu'interrompu — le
    # Dépannage explique pourquoi cela compte avec realtime=False.
    async for frame in ph.extract_audio_stream(
        "tone.wav",
        to_mono=False,
        target_sample_rate=44100,
        frame_ms=20,
        realtime=False,
    ):
        if first:
            print("shape", frame["pcm"].shape, "ndim", frame["pcm"].ndim)
            left, right = frame["pcm"][:, 0], frame["pcm"][:, 1]
            print("peak L", float(np.abs(left).max()), "peak R", float(np.abs(right).max()))
            first = False


asyncio.run(keep_channels())
```

```text
shape (882, 2) ndim 2
peak L 0.08837890625 peak R 0.08837890625
```

Branchez sur `pcm.ndim`, jamais sur le nombre d'échantillons : une source
**mono** lue avec `to_mono=False` revient quand même en 2-D, de forme
`(n_samples, 1)`. C'est délibéré, pour que `ndim` suffise à distinguer
« downmixé » de « canaux natifs préservés ». Il n'existe pas de réglage
`channels=N` : le downmix est canonique et déterministe, un upmix est un
choix créatif qui appartient à l'aval.

Une conséquence mesurée du downmix mérite d'être connue : la matrice
stéréo-vers-mono de ffmpeg pondère chaque canal à -3 dB, donc deux canaux
**identiques** s'additionnent à +3 dB. Un fichier stéréo corrélé à pleine
échelle est revenu avec un pic mono de `1,41`, en dehors de l'intervalle
`[-1.0, 1.0]` que promet la docstring de `PcmFrame`. Écrêtez ou réduisez le
gain si une étape en aval compte sur cette borne.

## 6. Le rééchantillonneur haute précision

Quand `target_sample_rate` diffère du débit de la source, c'est
`libswresample` de ffmpeg qui fait la conversion par défaut : un
rééchantillonneur polyphasé avec filtre passe-bas anti-repliement à la
nouvelle fréquence de Nyquist (`target_sample_rate / 2`). C'est correct au
sens de Shannon, largement suffisant pour la reconnaissance vocale, la
détection d'activité vocale et le machine learning.

`resample_quality="high"` bascule sur `libsoxr` en précision 28 bits
(`aresample=...:resampler=soxr:precision=28`), environ dix fois plus lent
pour des artefacts sous le seuil d'audition :

```python
async def audiophile():
    count = 0
    async for _frame in ph.extract_audio_stream(
        "tone.wav",
        target_sample_rate=48000,
        resample_quality="high",
        realtime=False,
    ):
        count += 1
    print("frames:", count)


asyncio.run(audiophile())
```

**Vérifiez d'abord votre build de ffmpeg.** `libsoxr` est une option de
compilation que le ffmpeg de Homebrew n'embarque pas. Sur la machine où
ces exemples ont tourné, l'extrait ci-dessus a affiché `frames: 0` et une
erreur ffmpeg dans le journal, sans lever d'exception :

```text
podcast-helper ffmpeg stderr: [Parsed_aresample_0 @ 0x...] [SWR @ 0x...] Requested resampling engine is unavailable
...
frames: 0
```

Avant de recourir à `resample_quality="high"`, confirmez donc que le moteur
est présent :

```bash
ffmpeg -hide_banner -version | grep -o -- --enable-libsoxr || echo "pas de libsoxr : restez sur le defaut"
```

Le chemin `libswresample` par défaut est toujours disponible, puisqu'il fait
partie de ffmpeg lui-même.

## 7. Une archive compressée pendant le flux

`record_to=` ajoute une seconde sortie au *même* processus ffmpeg : un
décodage, deux chemins d'encodage, aucun sous-processus supplémentaire.
L'archive s'écrit pendant que vous consommez le PCM ; elle reste cohérente
avec lui : même débit d'échantillonnage, même traitement des canaux, même
`speed`.

```python
import os


async def stream_and_keep():
    count = 0
    async for _frame in ph.extract_audio_stream(
        "tone.wav",
        target_sample_rate=16000,
        to_mono=True,
        realtime=False,
        record_to="tone.mp3",
    ):
        count += 1
    print("frames", count, "archive bytes", os.path.getsize("tone.mp3"))


asyncio.run(stream_and_keep())
```

```text
frames 50 archive bytes 17901
```

Le codec vient de l'extension : `.mp3` → libmp3lame 128 kbit/s,
`.m4a` / `.aac` → aac 128 kbit/s, `.opus` → libopus 96 kbit/s, `.ogg` →
libvorbis q5, `.flac` → flac sans perte, `.wav` → pcm_s16le. Tout le reste
lève `ValueError` avant même le démarrage de ffmpeg.

## 8. Alimenter un modèle en aval

Une trame de 20 ms est la bonne unité pour une détection d'activité vocale
et la mauvaise pour la plupart des modèles de reconnaissance vocale, qui
veulent une fenêtre d'une seconde ou plus. Le motif est toujours le même :
accumuler des trames, livrer une fenêtre, vider. Ici le modèle est un
bouchon qui rapporte ce qu'on lui a donné, pour que l'extrait tourne tel
quel :

```python
def transcribe(audio: np.ndarray) -> str:
    """Bouchon à la place d'un vrai appel ASR : rapporte ce qu'il a reçu."""
    return f"<{audio.size} samples, {audio.size / 16000:.2f}s>"


async def windowed(url, window_s=0.5):
    buffer: list[np.ndarray] = []
    elapsed = 0.0
    async for frame in ph.extract_audio_stream(
        url, target_sample_rate=16000, frame_ms=20, realtime=False
    ):
        buffer.append(frame["pcm"])
        elapsed += 0.020
        if elapsed >= window_s:
            print(f"t={frame['t_abs_s']:.2f}s {transcribe(np.concatenate(buffer))}")
            buffer.clear()
            elapsed = 0.0


asyncio.run(windowed("tone.wav"))
```

```text
t=0.48s <8000 samples, 0.50s>
t=0.98s <8000 samples, 0.50s>
```

Remplacez `transcribe` par `whisper.transcribe`, un appel à Silero VAD ou un
résumeur LLM : la forme de la boucle ne change pas. Deux détails valent pour
tout consommateur réel :

- `frame_ms=20` à 16 kHz fait 320 échantillons, la trame native de Silero
  VAD : une ingestion filtrée par VAD n'a donc aucun retamponnage à faire.
- `t_abs_s` est monotone depuis le début de la source, donc les horodatages
  que vous attachez à une transcription restent alignés sur l'épisode
  d'origine.

Pour de la VOD, vous pouvez aussi décoder plus vite que le temps réel avec
`speed=2.0` : la chaîne de filtres `atempo` préserve la hauteur, le modèle
ne reçoit donc pas des voix d'écureuil. L'appel lève `ValueError` sur une
source en direct.

## 9. La suite qui travaille ensemble

podcast-helper est un membre d'AI Helpers ; deux de ses compositions sont
réelles plutôt que déclaratives.

**os-helper tient la journalisation.** podcast-helper n'imprime jamais rien :
il passe par `osh.warning` et `osh.debug`. Monter le niveau fait apparaître
la commande ffmpeg exacte qu'il a construite, ce qui est la chose la plus
utile à avoir sous les yeux quand une source se comporte mal :

```python
osh.init_logging(level=logging.DEBUG)


async def show_command():
    async for _frame in ph.extract_audio_stream(
        "tone.wav", target_sample_rate=16000, realtime=False
    ):
        pass


asyncio.run(show_command())
```

```text
2026-10-27 13:01:42 | DEBUG | asyncio | Using selector: KqueueSelector
2026-10-27 13:01:42 | DEBUG | os_helper | podcast-helper: source=file is_live=False cmd=ffmpeg -hide_banner -loglevel error -nostdin -i tone.wav -ar 16000 -ac 1 -f f32le -
```

`osh.verbosity(2)` seul règle le niveau mais n'installe aucun gestionnaire,
donc rien n'apparaît ; c'est `osh.init_logging(...)` qui rend visibles les
lignes de journal de podcast-helper.

**vocal-helper consomme ce paquet.** Son extra `[stream]` dépend de
podcast-helper ; `vocal_helper.sources.from_url` enveloppe
`extract_audio_stream` en figeant le contrat dont ses étapes de parole ont
besoin — 16 kHz, mono, trames de 20 ms — tout en refusant délibérément
d'exposer ces trois réglages. Vérifié statiquement contre les sources de
vocal-helper, pas exécuté ici, puisque cela entraîne toute une pile de
traitement de la parole :

```python
# pip install "vocal-helper[stream]"
from vocal_helper.sources import from_url


async def ingest(url):
    # realtime laissé à sa valeur par défaut : voir le Dépannage sur le fait
    # de quitter une boucle realtime=False en avance.
    async for frame in from_url(url, record_to="episode.mp3"):
        print(frame["t_abs_s"], frame["pcm"].shape)
        break
```

`youtube-helper` est une dépendance déclarée de podcast-helper, mais notez
pour quoi : c'est elle qui amène la chaîne `yt-dlp` + ffmpeg dans
l'environnement. Le code de résolution de `streaming.py` appelle `yt_dlp`
directement, sans passer par l'API de youtube-helper.

## Ligne de commande

Une seule commande click, `podcast-helper`, avec cinq sous-commandes dont
les noms de drapeaux correspondent à ceux des surfaces HTTP et MCP : une
recette se transpose donc d'une porte à l'autre par copier-coller. Tout ce
qui suit a été exécuté.

```bash
podcast-helper --help
```

```text
Usage: podcast-helper [OPTIONS] COMMAND [ARGS]...

  Podcast Helper — any audio URL in, PCM frames or an archive out.

  Feeds, direct audio links, local files and every yt-dlp source (YouTube,
  SoundCloud, Twitch, ...) go in through the same --url.

Options:
  -V, --version  Show the version and exit.
  -h, --help     Show this message and exit.

Commands:
  feed    Dump an RSS / Atom podcast feed as JSON.
  latest  Print the latest episode's enclosure URL (or full Episode as...
  probe   Report how podcast-helper classified a URL.
  record  Archive any audio-bearing URL to a compressed file.
  stream  Decode any audio-bearing URL to raw f32le PCM on stdout, or a...
```

`probe` répond à la question « qu'as-tu décidé que cette URL était ? » sans
décoder un seul octet : c'est le moyen le plus rapide de déboguer une source
qui se comporte autrement que prévu.

```bash
podcast-helper probe --url tone.wav
```

```text
{
  "source_kind": "file",
  "is_live": false,
  "header_count": 0
}
```

`record` archive une source entière dans un fichier compressé puis imprime
le chemin écrit :

```bash
podcast-helper record --url tone.wav --output ep.mp3
```

```text
ep.mp3
```

`stream` écrit du PCM `f32le` brut sur la sortie standard, ce qui le rend
branchable sur ffplay, une détection d'activité vocale ou un frontal de
reconnaissance vocale. Une seconde à 16 kHz fait 16000 échantillons float32,
soit 64000 octets :

```bash
podcast-helper stream --url tone.wav --no-realtime --sample-rate 16000 | wc -c
```

```text
64000
```

`feed` et `latest` prennent une URL de flux et exigent le réseau :

```bash
podcast-helper feed   --url https://feeds.npr.org/510289/podcast.xml --max-episodes 5
podcast-helper latest --url https://feeds.npr.org/510289/podcast.xml --json
```

Les autres drapeaux à connaître : `--mono/--stereo`, `--frame-ms`,
`--speed` et `--realtime/--no-realtime` sur `stream` ; `--show-url` sur
`probe`, sur demande seulement puisqu'une URL résolue peut porter des jetons
signés. Les mêmes verbes sont servis en HTTP avec l'extra `[api]` (`uvicorn
podcast_helper.api:app`, GUI navigateur sur `/gui`) et comme outils MCP avec
`[mcp]` (`podcast-helper-mcp`, point d'accès `/mcp`).

## Dépannage

**Une source décode zéro trame sans que rien ne lève.** Quand ffmpeg
n'arrive pas à ouvrir l'entrée, l'itérateur se termine vide et la raison
part dans le journal plutôt que dans une exception. Vérifiez le compte de
trames :

```python
async def main():
    count = 0
    async for _frame in ph.extract_audio_stream("broken.mp3", realtime=False):
        count += 1
    print("frames:", count)


asyncio.run(main())
```

```text
podcast-helper ffmpeg stderr: [in#0 @ 0x...] Failed to find two consecutive MPEG audio frames.
[in#0 @ 0x...] Error opening input: Invalid data found when processing input
Error opening input file broken.mp3.
Error opening input files: Invalid data found when processing input
frames: 0
```

`resample_quality="high"` sur un ffmpeg sans `libsoxr` échoue de la même
façon silencieuse — voir la [section 6](#6-le-rééchantillonneur-haute-précision).

**Sortir en avance d'une boucle `realtime=False` peut bloquer.** Mesuré sur
un fichier local de 44,1 kHz d'une seconde : un `break` après la première
trame avec `realtime=False` a laissé le processus coincé à la fermeture du
générateur jusqu'à ce qu'on le tue, alors que le même code avec
`realtime=True` (le défaut) s'est terminé proprement, de même qu'une
consommation du flux jusqu'au bout. ffmpeg prend de l'avance sur le
consommateur ; le tube de sortie non lu laisse le nettoyage attendre une
fin de fichier qui n'arrive jamais. En attendant un correctif : épuisez
l'itérateur ou gardez le `realtime=True` par défaut si vous comptez vous
arrêter en avance.

**Les URL Spotify et Apple Podcasts sont refusées.** Délibérément et avant
toute requête réseau, avec le contournement dans le message :

```bash
podcast-helper probe --url https://open.spotify.com/episode/abc
```

```text
Error: Spotify-protected audio is DRM-gated and not retrievable through yt-dlp (or any reliable open tool). If this podcast has a public RSS feed (most do — check the show's website, getrssfeed.com, or Podcast Index), use the .mp3 enclosure URL directly. URL was: 'https://open.spotify.com/episode/abc'
```

**Un `max_episodes` négatif lève au lieu de découper.** `episodes[:-1]`
signifie « tous sauf le plus ancien » : un plafond négatif renvoyait donc
presque tout au lieu d'échouer.

```text
ValueError: max_episodes must be >= 0, got -1. A negative value would slice from the end of the list (dropping the oldest episodes) rather than capping the count.
```

**Une lecture réseau bloque.** ffmpeg n'applique aucun délai d'E/S sans
qu'on le lui demande : une connexion à moitié fermée est donc attendue
indéfiniment. Les sources réseau reçoivent `-rw_timeout` (60 s par défaut) ;
les fichiers locaux jamais, puisqu'un chemin sur disque ne peut pas se
bloquer sur une socket.

```bash
export PODCAST_HELPER_RW_TIMEOUT=120   # secondes ; 0 désactive la borne
```

Cela borne la lecture, cela ne rend pas le blocage impossible : une
exécution a été observée bloquée plus de quatre heures sur une URL
`googlevideo.com` qui portait bien `-rw_timeout` sur sa ligne de commande.
Un traitement qui doit aboutir a besoin d'une borne qui lui appartient — un
superviseur, un chien de garde — plutôt que de celle-ci.

**`FileNotFoundError` avant la première trame** signifie que `ffmpeg` n'est
pas sur le `PATH`. La bibliothèque l'appelle pour chaque source, fichiers
locaux compris.
