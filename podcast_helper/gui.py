"""
Podcast Helper — minimal single-page GUI ("episode browser").

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`podcast_helper.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. There is no bundler, no framework, no npm — the whole page is a
static asset the API returns verbatim.

Where the words live
--------------------
In the markup, in English. Each one is wrapped as ``{{_("…")}}`` in the HTML,
or listed in :data:`_JS_NAME_TO_SOURCE` for the script, and
:class:`os_helper.Catalog` translates it through the compiled ``gettext``
catalogues under ``locales/`` (``CODING.md`` 21.3).

English is the msgid, so it needs no catalogue and cannot fall out of sync with
one; a string the French catalogue has not caught up with renders as readable
English instead of as a key. The cost is the mirror image: rewording the
English here orphans its French entry, and gettext would quietly serve the
English. ``tests/test_gui_i18n.py`` exists to catch that — it hands every
source string to :meth:`os_helper.Catalog.problems`, so an orphaned
translation is a red build rather than a half-reverted page.

:func:`render_gui` resolves a language and returns the finished page.

Why a separate module
---------------------
Keeping the (long) HTML out of :mod:`podcast_helper.api` keeps the route
definitions readable and mirrors the AI Helpers suite convention (see
``audio_helper/gui.py``): sibling repos copy the plumbing and swap the domain
widgets. Here the domain widget is a **feed / episode browser**, not an audio
"audition bench".

What the page does
------------------
- Enter any feed / RSS / audio / yt-dlp URL in a single box.
- **List episodes** (calls ``GET /feed``) → a scrollable list of episode cards
  with cover art, title, publish date and duration.
- **Probe** any URL (calls ``GET /probe``) → shows how podcast-helper classified
  it (source_kind / is_live / header count) so ambiguity is never buried.
- Pick an episode → its metadata renders on the right, its ``enclosure_url``
  loads into an inline ``<audio>`` player for instant preview (the browser
  streams the enclosure directly — no server round-trip for playback).
- **Record** the selected episode (or any raw URL) to a compressed archive via
  ``POST /record`` and offer the resulting file as a download.

Everything talks to the SAME FastAPI endpoints the CLI surface uses —
the GUI adds zero new server logic and never uploads the user's data anywhere.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import functools
import html
import json
import re
from pathlib import Path

import os_helper as osh

# Inside the package, not beside it: a file one level up is not package data
# and does not travel in the wheel. best-engine shipped exactly that bug —
# `pip install` gave a package whose every GUI string raised FileNotFoundError.
_LOCALES_DIR = Path(__file__).resolve().parent / "locales"

#: The gettext domain, and therefore each ``.mo`` file's stem.
_DOMAIN = "podcast_helper"

#: The language served when the request names one we cannot render.
_DEFAULT_LANGUAGE = "fr"


@functools.lru_cache(maxsize=1)
def _catalog() -> osh.Catalog:
    """Resolve the catalogue directory once, through the suite's shared loader."""
    return osh.Catalog.from_package(_LOCALES_DIR, _DOMAIN, default_language=_DEFAULT_LANGUAGE)


def supported_languages() -> tuple[str, ...]:
    """Language codes the GUI can render: English plus every compiled catalogue."""
    return _catalog().languages


def default_language() -> str:
    """The language an unknown or absent ``?lang=`` falls back to."""
    return _catalog().default_language


# The language toggle is computed, not translated. Its three parts all mean
# "the other language", which is data rather than copy: a msgid of
# ``/gui?lang=fr`` whose translation is ``/gui?lang=en`` would be nonsense, and
# `Catalog.problems` would rightly treat it as prose that had drifted.
#
#: Flag shown for a language — the flag of that language, not of the page.
_FLAGS: dict[str, str] = {"fr": "🇫🇷", "en": "🇬🇧"}

#: How each language names itself. Deliberately NOT translated: a French page
#: offering English says "English version" in English, which is what a reader
#: scanning for their own language actually looks for.
_ENDONYMS: dict[str, str] = {"fr": "Version française", "en": "English version"}


# The inline script's strings. The JS names are the contract between this
# module and the script below; the English beside each one is the msgid, so
# the script's copy lives in the same place as the markup's and is checked
# by the same test. Injected as JSON, which is the one encoding an
# apostrophe cannot break out of — and French copy is full of them.
_JS_NAME_TO_SOURCE: dict[str, str] = {
    "needFeedUrl": "Enter a feed URL first.",
    "fetchingFeed": "Fetching feed…",
    "errorPrefix": "Error ",
    "noEpisodesItem": "No episodes found in this feed.",
    "feedNoEpisodes": "Feed parsed but no episodes.",
    "selected": "Selected: {title}",
    "listed": "Listed {count} episode(s).",
    "requestFailed": "Request failed: {error}",
    "needProbeUrl": "Enter a URL to probe first.",
    "probing": "Probing…",
    "probeHeading": "Probe result",
    "classified": "Classified as {kind}{live}.",
    "liveSuffix": " (live)",
    "needRecordTarget": "Select an episode or enter a URL to record.",
    "recording": "Recording (server-side ffmpeg)… this can take a while for long episodes.",
    "recordDone": "Done — archive ready to download.",
}


#: One ``{{_("…")}}`` site in the template. Non-greedy and newline-free, so a
#: run of them on one line stays separate and an unterminated one is left
#: alone rather than swallowing the rest of the page.
_SOURCE_RE = re.compile(r'\{\{_\("(.*?)"\)\}\}')

_GUI_TEMPLATE: str = r"""<!doctype html>
<html lang="{{LANG}}" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{_("Podcast Helper — Episode Browser")}}</title>
  <!-- Tailwind via CDN: keeps the page a single self-contained file, no build. -->
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Respect users who ask for reduced motion (accessibility baseline). */
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  </style>
</head>
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  <div class="mx-auto max-w-5xl px-4 py-8">
    <header class="mb-6">
      <!-- Language toggle: a flag that links to the other locale of this page. -->
      <a href="{{LANG_HREF}}" aria-label="{{LANG_ARIA}}"
         class="float-right text-xl hover:opacity-70">{{LANG_FLAG}}</a>
      <h1 class="text-2xl font-semibold tracking-tight">{{_("Podcast Helper — Episode Browser")}}</h1>
      <p class="mt-1 text-sm text-slate-600">
        {{_("Paste a feed / RSS / audio / YouTube URL, list its episodes, preview one inline, and archive it to a file — all on your local machine.")}}
      </p>
    </header>

    <!-- 1) URL box + the three primary actions. -->
    <section class="mb-5">
      <label for="url" class="block text-sm font-medium mb-1">{{_("Feed / RSS / audio / yt-dlp URL")}}</label>
      <div class="flex flex-col gap-2 sm:flex-row">
        <input id="url" type="url" placeholder="https://feeds.npr.org/510289/podcast.xml"
               class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm
                      focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <div class="flex gap-2">
          <!-- List episodes: only meaningful for an RSS/Atom feed URL. -->
          <button id="list"
                  class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white
                         hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500
                         disabled:opacity-50">
            {{_("List episodes")}}
          </button>
          <!-- Probe: classify any URL (file / direct / rss / yt-dlp-<extractor>). -->
          <button id="probe"
                  class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold
                         text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2
                         focus:ring-blue-500 disabled:opacity-50">
            {{_("Probe")}}
          </button>
        </div>
      </div>
      <span id="status" class="mt-2 block text-sm text-slate-600" role="status" aria-live="polite"></span>
    </section>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <!-- 2) Left column: the episode list (populated by /feed). -->
      <section class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">{{_("Episodes")}}</h2>
        <ul id="episodes" class="max-h-96 space-y-2 overflow-y-auto text-sm">
          <li class="text-slate-400">{{_("List a feed to see its episodes here.")}}</li>
        </ul>
      </section>

      <!-- 3) Right column: selected episode metadata + inline player + record. -->
      <section class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">{{_("Selected")}}</h2>
        <div id="meta" class="text-sm text-slate-500">
          {{_("Pick an episode on the left, or probe / record a raw URL directly.")}}
        </div>

        <!-- Inline preview: browser plays the enclosure_url directly. -->
        <div class="mt-3">
          <label class="block text-xs font-medium mb-1">{{_("Preview")}}</label>
          <audio id="player" controls class="w-full"></audio>
        </div>

        <!-- Record controls: archive the selected episode (or the URL box). -->
        <div class="mt-4 grid grid-cols-2 gap-3">
          <div>
            <label for="fmt" class="block text-xs font-medium mb-1">{{_("record format")}}</label>
            <select id="fmt"
                    class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
              <option value="mp3">mp3</option>
              <option value="m4a">m4a</option>
              <option value="opus">opus</option>
              <option value="ogg">ogg</option>
              <option value="flac">flac</option>
              <option value="wav">wav</option>
            </select>
          </div>
          <div>
            <label for="rate" class="block text-xs font-medium mb-1">{{_("sample rate (Hz)")}}</label>
            <input id="rate" type="number" value="16000"
                   class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
        </div>
        <div class="mt-3 flex items-center gap-3">
          <button id="record"
                  class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white
                         hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500
                         disabled:opacity-50">
            {{_("Record to file")}}
          </button>
          <a id="download" class="inline-block text-sm font-medium text-blue-600 hover:underline"
             hidden download>{{_("Download archive")}}</a>
        </div>
      </section>
    </div>
  </div>

  <script type="module">
    // Every human-readable string the script writes comes from the locale
    // file, injected as JSON — the one encoding an apostrophe cannot break
    // out of, and French copy is full of them.
    const T = {{T_JSON}};

    // --- tiny DOM helpers -------------------------------------------------
    const $ = (id) => document.getElementById(id);
    const status = (msg) => { $("status").textContent = msg; };

    // The URL of the currently-selected target: an episode enclosure when one
    // is picked, otherwise whatever is in the URL box (raw URL workflows).
    let selectedUrl = "";

    // --- helpers ----------------------------------------------------------
    // Escape user-controlled feed text before injecting it into innerHTML so a
    // malicious feed title can never inject markup into the page.
    function esc(s) {
      return String(s ?? "").replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
      ));
    }

    // Format an integer number of seconds as H:MM:SS / M:SS for the cards.
    function fmtDuration(sec) {
      sec = Number(sec) || 0;
      if (!sec) return "";
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = Math.floor(sec % 60);
      const mm = String(m).padStart(h ? 2 : 1, "0");
      const ss = String(s).padStart(2, "0");
      return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
    }

    // Load a URL into the inline <audio> player and remember it as the target.
    function selectUrl(u, label) {
      selectedUrl = u;
      $("player").src = u;
      $("meta").innerHTML = label;
    }

    // --- List episodes: GET /feed?url=... --------------------------------
    $("list").addEventListener("click", async () => {
      const url = $("url").value.trim();
      if (!url) { status(T.needFeedUrl); return; }
      status(T.fetchingFeed);
      $("list").disabled = true;
      try {
        const res = await fetch("/feed?url=" + encodeURIComponent(url));
        if (!res.ok) {
          const txt = await res.text();
          status(T.errorPrefix + res.status + ": " + txt.slice(0, 200));
          return;
        }
        const data = await res.json();
        const episodes = data.episodes || [];
        const ul = $("episodes");
        ul.innerHTML = "";
        if (!episodes.length) {
          // Built as a node rather than spliced into innerHTML: the text comes
          // from the locale file, and a translation is copy, never markup.
          const empty = document.createElement("li");
          empty.className = "text-slate-400";
          empty.textContent = T.noEpisodesItem;
          ul.appendChild(empty);
          status(T.feedNoEpisodes);
          return;
        }
        // Render one clickable card per episode. Clicking selects it: loads its
        // enclosure into the player and shows its metadata on the right.
        for (const ep of episodes) {
          const li = document.createElement("li");
          li.className =
            "cursor-pointer rounded-lg border border-slate-200 p-2 hover:border-blue-400 hover:bg-slate-50";
          const date = (ep.published_at || "").slice(0, 10);
          const dur = fmtDuration(ep.duration_seconds);
          li.innerHTML =
            '<div class="flex gap-2">' +
            (ep.image_url
              ? '<img src="' + esc(ep.image_url) + '" alt="" class="h-10 w-10 rounded object-cover" />'
              : "") +
            '<div class="min-w-0">' +
            '<div class="truncate font-medium">' + esc(ep.title) + "</div>" +
            '<div class="text-xs text-slate-500">' +
            esc(date) + (dur ? " · " + esc(dur) : "") + "</div>" +
            "</div></div>";
          li.addEventListener("click", () => {
            // Remember the enclosure and render the metadata panel.
            selectUrl(
              ep.enclosure_url,
              '<div class="font-medium">' + esc(ep.title) + "</div>" +
              '<div class="mt-1 text-xs text-slate-500">' +
              esc(ep.published_at || "") + (dur ? " · " + esc(dur) : "") + "</div>" +
              (ep.description
                ? '<div class="mt-2 max-h-32 overflow-y-auto text-xs text-slate-600">' +
                  esc(ep.description).slice(0, 800) + "</div>"
                : "")
            );
            status(T.selected.replace("{title}", ep.title));
          });
          ul.appendChild(li);
        }
        // Named fields, not concatenation: a translator can reorder the
        // sentence instead of inheriting the order JavaScript glued it in.
        status(T.listed.replace("{count}", episodes.length));
      } catch (err) {
        status(T.requestFailed.replace("{error}", err));
      } finally {
        $("list").disabled = false;
      }
    });

    // --- Probe: GET /probe?url=... ---------------------------------------
    $("probe").addEventListener("click", async () => {
      const url = $("url").value.trim();
      if (!url) { status(T.needProbeUrl); return; }
      status(T.probing);
      $("probe").disabled = true;
      try {
        const res = await fetch("/probe?url=" + encodeURIComponent(url));
        if (!res.ok) {
          const txt = await res.text();
          status(T.errorPrefix + res.status + ": " + txt.slice(0, 200));
          return;
        }
        const j = await res.json();
        // Treat the probed URL as the current target so Record works on it,
        // and if it is a directly playable enclosure, load it in the player.
        selectedUrl = url;
        if (j.source_kind === "direct_audio" || j.source_kind === "file") {
          $("player").src = url;
        }
        $("meta").innerHTML =
          '<div class="font-medium">' + esc(T.probeHeading) + "</div>" +
          '<pre class="mt-2 rounded bg-slate-100 p-2 text-xs">' +
          esc(JSON.stringify(j, null, 2)) + "</pre>";
        status(T.classified
          .replace("{kind}", j.source_kind)
          .replace("{live}", j.is_live ? T.liveSuffix : ""));
      } catch (err) {
        status(T.requestFailed.replace("{error}", err));
      } finally {
        $("probe").disabled = false;
      }
    });

    // --- Record: POST /record (multipart form) ---------------------------
    $("record").addEventListener("click", async () => {
      // Prefer the selected episode; fall back to the raw URL box.
      const target = selectedUrl || $("url").value.trim();
      if (!target) { status(T.needRecordTarget); return; }
      const fmt = $("fmt").value;
      const rate = $("rate").value;
      const fd = new FormData();
      fd.append("url", target);
      fd.append("output_format", fmt);
      fd.append("sample_rate", rate);
      status(T.recording);
      $("record").disabled = true;
      $("download").hidden = true;
      try {
        const res = await fetch("/record", { method: "POST", body: fd });
        if (!res.ok) {
          const txt = await res.text();
          status(T.errorPrefix + res.status + ": " + txt.slice(0, 200));
          return;
        }
        // The response body is the archive file: wrap it in an object URL.
        const blob = await res.blob();
        const dl = $("download");
        dl.href = URL.createObjectURL(blob);
        dl.download = "episode." + fmt;
        dl.hidden = false;
        status(T.recordDone);
      } catch (err) {
        status(T.requestFailed.replace("{error}", err));
      } finally {
        $("record").disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def render_gui(lang: str = "") -> str:
    """Render the single-page GUI in the requested language.

    Parameters
    ----------
    lang : str
        Two-letter language code. Anything outside the locale file's
        a compiled catalogue — including the empty string — falls back
        to ``meta.default_locale``, so an unknown ``?lang=`` never 500s.

    Returns
    -------
    str
        The complete HTML document for that language.

    Examples
    --------
    >>> "<!doctype html>" in render_gui("en")
    True
    >>> render_gui("tlh") == render_gui(default_language())
    True
    """
    cat = _catalog()
    resolved = cat.resolve(lang)
    translate = cat.translator_for(resolved).gettext

    # The other language, for the toggle. With two languages this is "the one
    # that is not current"; with more it is the next one round, which keeps the
    # flag a cycle rather than a dead end.
    languages = cat.languages
    other = languages[(languages.index(resolved) + 1) % len(languages)]

    def _render_source(match: re.Match[str]) -> str:
        """Translate one ``{{_("…")}}`` site and escape it for HTML.

        Escaping is not optional: these land in attributes (placeholder, alt,
        aria, title) as readily as in text nodes, and a French apostrophe in an
        attribute would close it early.
        """
        return html.escape(translate(match.group(1)), quote=True)

    page = _SOURCE_RE.sub(_render_source, _GUI_TEMPLATE)
    page = page.replace("{{LANG}}", html.escape(resolved, quote=True))
    page = page.replace("{{LANG_HREF}}", html.escape(f"/gui?lang={other}", quote=True))
    page = page.replace("{{LANG_FLAG}}", _FLAGS.get(other, other.upper()))
    page = page.replace("{{LANG_ARIA}}", html.escape(_ENDONYMS.get(other, other), quote=True))

    # The script's strings go in as JSON rather than as substituted text: it is
    # the encoding that cannot be broken out of by an apostrophe, and French
    # copy is full of them.
    table = {name: translate(source) for name, source in _JS_NAME_TO_SOURCE.items()}
    return page.replace("{{T_JSON}}", json.dumps(table, ensure_ascii=False))


def __getattr__(name: str) -> str:
    """Serve ``GUI_HTML`` on first access rather than building it at import.

    The module-level constant used to BE the page, and importers still reach
    for it. Assigning it eagerly would read and parse the locale file on every
    import of this module, including in callers that never serve the GUI — and
    a module-level ``__getattr__`` only fires for names that are NOT otherwise
    defined, so the name is deliberately left unbound rather than set to a
    placeholder.
    """
    if name == "GUI_HTML":
        return render_gui()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
