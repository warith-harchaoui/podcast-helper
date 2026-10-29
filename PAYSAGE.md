# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/LANDSCAPE.md)

Bibliothèques Python voisines et concurrentes dans l'espace « consommer
une URL de podcast / d'audio et livrer du PCM ou des métadonnées »,
comparées à `podcast-helper`. Les notes vont de ⭐ (1) à ⭐⭐⭐⭐⭐ (5),
évaluées sur la tâche visée par `podcast-helper` : URL en entrée, PCM
en sortie pour les pipelines d'IA (fichiers, enclosures directes,
flux RSS / Atom, sources prises en charge par yt-dlp), avec une correction
du traitement du signal et une ergonomie pragmatique. Une bibliothèque
optimisée pour un tout autre usage (par exemple gestion de podcasts hors ligne,
lecture RSS généraliste, montage audio façon station de travail) n'est pas
pénalisée : la note reflète seulement l'adéquation à *ce* créneau.

## En un coup d'œil

<!-- TABLE:START -->
| Ingestion audio | URL universelle en entrée | Analyse RSS / Atom | Résolution yt-dlp | Flux en direct (HLS) | Rééchantillonnage correct | Streaming PCM | Archive compressée | Multi-surface |
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

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/paysage.png)

La carte est un résumé en 2D des 8 critères : à lire comme une forme, pas comme un classement. « podcast-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal : Pertinence ↔ Efficacité** et **Vertical : Clarté ↔ Richesse**.
<!-- FIGURE:END -->

## Positionnement

`podcast-helper` se place volontairement à l'intersection d'une **couverture
d'URL au niveau de yt-dlp** (n'importe quelle URL web porteuse d'audio, plus
les fichiers, les enclosures directes et les flux RSS) et des **besoins des
pipelines d'IA** (itérateur PCM asynchrone avec rééchantillonnage correct au
sens de Shannon, downmix mono ou canaux natifs préservés, archive compressée
parallèle optionnelle). Il ne cherche délibérément *pas* à concurrencer
`podcastparser` / `feedparser` sur le terrain de l'analyse de flux : il
utilise les deux, avec `podcastparser` en principal et `feedparser` en
secours pour les variantes Atom exotiques et garde `yt-dlp` comme
intégration optionnelle mais incluse pour tout ce que le routage par
extension ne parvient pas à classer.

Le principal différenciateur face à yt-dlp lui-même est l'**itérateur
asynchrone de trames PCM**, qui laisse un consommateur en aval (ASR / VAD /
diarisation) tirer les trames exactement au rythme de la source (ou aussi
vite que possible) sans jamais toucher le disque. Le principal différenciateur
face à `podcastparser` / `feedparser` est qu'une URL de flux se résout
directement en URL porteuse d'audio : l'appelant n'a pas à parcourir
lui-même la liste des enclosures.

La correction du rééchantillonnage est le détail le plus discret mais le plus
déterminant : `podcast-helper` rééchantillonne via `swresample` / `soxr` de
ffmpeg, de sorte qu'un modèle en aval voit toujours du PCM à bande limitée,
sans repliement. Une chaîne artisanale `requests + ffmpeg` peut atteindre la
même fidélité, mais laisse tout le reste (routage, flux, itérateur de
streaming, archive) à la charge de l'appelant.

## Quand choisir quoi

- **`podcast-helper`** : ingestion audio pour les pipelines de podcasts d'IA,
  transcription par lots, réglage de VAD, curation de jeux de données, ASR sur
  flux en direct, rééchantillonnage correct au sens de Shannon avec une archive
  compressée optionnelle.
- **`yt-dlp`** : vous avez seulement besoin du fichier sur disque et vous ne
  vous souciez ni du RSS ni du streaming asynchrone.
- **`streamlink`** : vous avez précisément besoin de récupérer un flux HLS en
  direct et rien d'autre.
- **`feedparser` / `podcastparser`** : vous avez seulement besoin de parcourir
  les métadonnées d'un flux ; l'ingestion audio est hors périmètre.
- **`pydub` / `librosa` / `audioread`** : vous avez déjà le fichier et vous
  voulez manipuler ou décoder ses échantillons avec une bibliothèque audio mature.
- **`ffmpeg-python` ou `requests` + `ffmpeg` à la main** : vous ne voulez que
  le décodage et rien d'autre, puis vous acceptez d'assumer vous-même le
  routage d'URL, le parcours des flux et le découpage en trames. C'est l'alternative
  honnête à ce paquet : `podcast-helper` est précisément ces trois soucis-là
  plus un itérateur asynchrone, pas un meilleur décodeur.

## Sources et date de relevé

Relevé le **27 octobre 2026**.

La ligne `podcast-helper` est notée d'après le code de ce dépôt en
**v1.6.0** : `podcast_helper/streaming.py` pour la classification d'URL, la
commande ffmpeg puis l'archive parallèle ; `podcast_helper/feed.py` pour
l'analyse RSS et Atom (podcastparser d'abord, feedparser en secours) ; enfin
les cinq surfaces que liste le README.

Quatre des autres lignes ont été relevées sur les versions réellement
installées dans l'environnement de ce dépôt à cette date, plutôt que dans un
journal de versions : `yt-dlp 2026.6.9`, `feedparser 6.0.12`,
`podcastparser 0.6.11` puis `ffmpeg-python 0.2.0`. Le comportement de
décodage a été vérifié avec `ffmpeg 8.1.2`.

Les lignes restantes — `streamlink`, `pytube`, `pydub`, `librosa`,
`audioread` — ne sont **pas installées ici**. Elles sont notées d'après le
périmètre que revendique leur propre documentation, aucune version ne leur
est attribuée et rien n'a été mesuré contre elles. Les étoiles sont un
jugement d'adéquation à un créneau, pas une mesure ; un désaccord mérite une
issue, pas la correction d'un chiffre.

Deux réserves accompagnent le tableau plutôt qu'elles ne le suivent :

- Les cinq étoiles en « Rééchantillonnage correct » sont héritées de
  `libswresample` de ffmpeg, qui fait le travail réel. Le chemin optionnel
  `resample_quality="high"` exige un ffmpeg compilé avec
  `--enable-libsoxr`, que le build Homebrew standard n'embarque pas : mesuré
  ici, il rend zéro trame.
- « Multi-surface » compte des portes, pas de la maturité : bibliothèque,
  CLI, API FastAPI, GUI navigateur puis MCP existent toutes et sont testées,
  mais une bibliothèque monotâche notée une étoile n'en fait pas moins bien
  son propre travail.

## Idées à reprendre

Étudié plutôt que deviné : ce que chaque voisin fait mieux, puis ce que cette bibliothèque devrait changer pour l'égaler. Rien ici n'est un engagement : c'est la liste de lecture dont part la version suivante.

- **L'espace de noms Podcast 2.0 — chapitres, transcriptions, financement, extraits** — `feedparser` lit le RSS avec l'espace de noms iTunes ; c'est dans l'espace Podcast 2.0 que vivent les chapitres puis les transcriptions publiées, or une transcription déjà présente dans le flux est un travail que cette suite refait sinon avec un GPU.

- **`podcastparser` — un analyseur en flux taillé pour les flux de podcast** — Il analyse au fil de l'eau puis vise spécifiquement les flux de podcast, là où `feedparser` construit tout le document. Pour un gros flux lu seulement afin de trouver le dernier épisode, c'est la forme la moins chère.

- **`streamlink` — un épisode en direct n'est pas un fichier** — Même leçon que celle déjà inscrite dans le jumeau Rust : résoudre vers une adresse pour un média sans fin, plutôt que d'essayer de le télécharger.

- **OPML — un abonnement est une liste, puis la liste a un format** — Importer puis exporter de l'OPML est la façon dont tout client de podcast déplace un jeu d'abonnements. Une bibliothèque qui résout les flux un par un n'est qu'à une fonction de traiter l'ensemble.
