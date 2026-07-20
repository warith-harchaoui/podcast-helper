"""
Podcast Helper — minimal single-page GUI ("episode browser").

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`podcast_helper.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. There is no bundler, no framework, no npm — the whole page is a
static asset the API returns verbatim.

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

Everything talks to the SAME FastAPI endpoints the CLI and MCP surfaces use —
the GUI adds zero new server logic and never uploads the user's data anywhere.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

# The entire GUI is this one HTML string. It is returned as-is by the
# ``/gui`` route. Tailwind is pulled from a CDN so there is no build step;
# the JavaScript is a single inline ES module talking to the existing API.
GUI_HTML: str = r"""<!doctype html>
<html lang="en" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Podcast Helper — Episode Browser</title>
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
      <h1 class="text-2xl font-semibold tracking-tight">Podcast Helper — Episode Browser</h1>
      <p class="mt-1 text-sm text-slate-600">
        Paste a feed / RSS / audio / YouTube URL, list its episodes, preview one
        inline, and archive it to a file — all on your local machine.
      </p>
    </header>

    <!-- 1) URL box + the three primary actions. -->
    <section class="mb-5">
      <label for="url" class="block text-sm font-medium mb-1">Feed / RSS / audio / yt-dlp URL</label>
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
            List episodes
          </button>
          <!-- Probe: classify any URL (file / direct / rss / yt-dlp-<extractor>). -->
          <button id="probe"
                  class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold
                         text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2
                         focus:ring-blue-500 disabled:opacity-50">
            Probe
          </button>
        </div>
      </div>
      <span id="status" class="mt-2 block text-sm text-slate-600" role="status" aria-live="polite"></span>
    </section>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <!-- 2) Left column: the episode list (populated by /feed). -->
      <section class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">Episodes</h2>
        <ul id="episodes" class="max-h-96 space-y-2 overflow-y-auto text-sm">
          <li class="text-slate-400">List a feed to see its episodes here.</li>
        </ul>
      </section>

      <!-- 3) Right column: selected episode metadata + inline player + record. -->
      <section class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">Selected</h2>
        <div id="meta" class="text-sm text-slate-500">
          Pick an episode on the left, or probe / record a raw URL directly.
        </div>

        <!-- Inline preview: browser plays the enclosure_url directly. -->
        <div class="mt-3">
          <label class="block text-xs font-medium mb-1">Preview</label>
          <audio id="player" controls class="w-full"></audio>
        </div>

        <!-- Record controls: archive the selected episode (or the URL box). -->
        <div class="mt-4 grid grid-cols-2 gap-3">
          <div>
            <label for="fmt" class="block text-xs font-medium mb-1">record format</label>
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
            <label for="rate" class="block text-xs font-medium mb-1">sample rate (Hz)</label>
            <input id="rate" type="number" value="16000"
                   class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
        </div>
        <div class="mt-3 flex items-center gap-3">
          <button id="record"
                  class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white
                         hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500
                         disabled:opacity-50">
            Record to file
          </button>
          <a id="download" class="inline-block text-sm font-medium text-blue-600 hover:underline"
             hidden download>Download archive</a>
        </div>
      </section>
    </div>
  </div>

  <script type="module">
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
      if (!url) { status("Enter a feed URL first."); return; }
      status("Fetching feed…");
      $("list").disabled = true;
      try {
        const res = await fetch("/feed?url=" + encodeURIComponent(url));
        if (!res.ok) {
          const txt = await res.text();
          status("Error " + res.status + ": " + txt.slice(0, 200));
          return;
        }
        const data = await res.json();
        const episodes = data.episodes || [];
        const ul = $("episodes");
        ul.innerHTML = "";
        if (!episodes.length) {
          ul.innerHTML = '<li class="text-slate-400">No episodes found in this feed.</li>';
          status("Feed parsed but no episodes.");
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
            status("Selected: " + ep.title);
          });
          ul.appendChild(li);
        }
        status("Listed " + episodes.length + " episode(s).");
      } catch (err) {
        status("Request failed: " + err);
      } finally {
        $("list").disabled = false;
      }
    });

    // --- Probe: GET /probe?url=... ---------------------------------------
    $("probe").addEventListener("click", async () => {
      const url = $("url").value.trim();
      if (!url) { status("Enter a URL to probe first."); return; }
      status("Probing…");
      $("probe").disabled = true;
      try {
        const res = await fetch("/probe?url=" + encodeURIComponent(url));
        if (!res.ok) {
          const txt = await res.text();
          status("Error " + res.status + ": " + txt.slice(0, 200));
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
          '<div class="font-medium">Probe result</div>' +
          '<pre class="mt-2 rounded bg-slate-100 p-2 text-xs">' +
          esc(JSON.stringify(j, null, 2)) + "</pre>";
        status("Classified as " + j.source_kind + (j.is_live ? " (live)" : "") + ".");
      } catch (err) {
        status("Request failed: " + err);
      } finally {
        $("probe").disabled = false;
      }
    });

    // --- Record: POST /record (multipart form) ---------------------------
    $("record").addEventListener("click", async () => {
      // Prefer the selected episode; fall back to the raw URL box.
      const target = selectedUrl || $("url").value.trim();
      if (!target) { status("Select an episode or enter a URL to record."); return; }
      const fmt = $("fmt").value;
      const rate = $("rate").value;
      const fd = new FormData();
      fd.append("url", target);
      fd.append("output_format", fmt);
      fd.append("sample_rate", rate);
      status("Recording (server-side ffmpeg)… this can take a while for long episodes.");
      $("record").disabled = true;
      $("download").hidden = true;
      try {
        const res = await fetch("/record", { method: "POST", body: fd });
        if (!res.ok) {
          const txt = await res.text();
          status("Error " + res.status + ": " + txt.slice(0, 200));
          return;
        }
        // The response body is the archive file: wrap it in an object URL.
        const blob = await res.blob();
        const dl = $("download");
        dl.href = URL.createObjectURL(blob);
        dl.download = "episode." + fmt;
        dl.hidden = false;
        status("Done — archive ready to download.");
      } catch (err) {
        status("Request failed: " + err);
      } finally {
        $("record").disabled = false;
      }
    });
  </script>
</body>
</html>
"""
