# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/LANDSCAPE.md)

Bibliothèques Python voisines et concurrentes dans l'espace « consommer
une URL de podcast / d'audio et livrer du PCM ou des métadonnées »,
comparées à `podcast-helper`. Les notes vont de ⭐ (1) à ⭐⭐⭐⭐⭐ (5),
évaluées sur la tâche visée par `podcast-helper` — universel URL-en-entrée
→ PCM-en-sortie pour les pipelines d'IA (fichiers, enclosures directes,
flux RSS / Atom, sources prises en charge par yt-dlp), avec une correction
du traitement du signal et une ergonomie pragmatique. Une bibliothèque
optimisée pour un tout autre usage (par ex. gestion de podcasts hors ligne,
lecture RSS généraliste, montage audio façon station de travail) n'est pas
pénalisée — la note reflète seulement l'adéquation à *ce* créneau.

## En un coup d'œil

| Ingestion audio | URL universelle en entrée | Analyse RSS / Atom | Résolution yt-dlp | Flux en direct (HLS) | Rééchantillonnage correct | Streaming PCM | Archive compressée | Multi-surface |
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

## Carte de positionnement

Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/paysage.png)

La carte est un résumé en 2D des 8 critères : à lire comme une forme, pas comme un classement. « podcast-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Analyse ↔ Compress** et **Vertical — Chantillonnage ↔ Surface**.

## Positionnement

`podcast-helper` se place volontairement à l'intersection d'une **couverture
d'URL au niveau de yt-dlp** (n'importe quelle URL web porteuse d'audio, plus
les fichiers, les enclosures directes et les flux RSS) et des **besoins des
pipelines d'IA** (itérateur PCM asynchrone avec rééchantillonnage correct au
sens de Shannon, downmix mono ou canaux natifs préservés, archive compressée
parallèle optionnelle). Il ne cherche délibérément *pas* à concurrencer
`podcastparser` / `feedparser` sur le terrain de l'analyse de flux — il
utilise les deux, avec `podcastparser` en principal et `feedparser` en
secours pour les variantes Atom exotiques — et garde `yt-dlp` comme
intégration optionnelle mais incluse pour tout ce que le routage par
extension ne parvient pas à classer.

Le principal différenciateur face à yt-dlp lui-même est l'**itérateur
asynchrone de trames PCM**, qui laisse un consommateur en aval (ASR / VAD /
diarisation) tirer les trames exactement au rythme de la source (ou aussi
vite que possible) sans jamais toucher le disque. Le principal différenciateur
face à `podcastparser` / `feedparser` est qu'une URL de flux devient de façon
transparente une URL porteuse d'audio — l'appelant n'a pas à parcourir
lui-même la liste des enclosures.

La correction du rééchantillonnage est l'arête la plus discrète mais la plus
déterminante : `podcast-helper` rééchantillonne via `swresample` / `soxr` de
ffmpeg, de sorte qu'un modèle en aval voit toujours du PCM à bande limitée,
sans repliement. Une chaîne artisanale `requests + ffmpeg` peut atteindre la
même fidélité, mais laisse toutes les autres préoccupations (routage, flux,
itérateur de streaming, archive) à la charge de l'appelant.

## Quand choisir quoi

- **`podcast-helper`** — ingestion audio pour les pipelines de podcasts d'IA :
  transcription par lots, réglage de VAD, curation de jeux de données, ASR sur
  flux en direct, rééchantillonnage correct au sens de Shannon avec une archive
  compressée optionnelle.
- **`yt-dlp`** — vous avez seulement besoin du fichier sur disque et vous ne
  vous souciez ni du RSS ni du streaming asynchrone.
- **`feedparser` / `podcastparser`** — vous avez seulement besoin de parcourir
  les métadonnées d'un flux ; l'ingestion audio est hors périmètre.
- **`gPodder`** — vous voulez un client de podcast de bureau avec un magasin
  d'abonnements.
- **`pydub` / `librosa` / `soundfile`** — vous avez déjà le fichier et vous
  voulez manipuler ses échantillons avec une bibliothèque audio mature.
