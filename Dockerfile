# syntax=docker/dockerfile:1.6
#
# podcast-helper — reproducible container image.
#
# Two-stage build: the base stage pulls system deps (ffmpeg is
# mandatory for the whole toolkit) and installs the package with the
# [api,mcp] extras so the container can serve the HTTP + MCP surfaces
# out of the box.
#
# Build:
#   docker build -t podcast-helper .
#
# Run (HTTP + MCP on 0.0.0.0:8000):
#   docker run --rm -p 8000:8000 podcast-helper
#
# Run CLI one-shot:
#   docker run --rm -v $PWD:/data podcast-helper \
#     podcast-helper record --url https://feeds.npr.org/510289/podcast.xml \
#                           --output /data/latest.mp3

# --- base -------------------------------------------------------------------
FROM python:3.11-slim AS base

# System deps: ffmpeg for every audio pipeline, libsndfile for parity
# with the AI-helpers family that shares this image, tini for signal
# handling. No compilers — we install from wheels only.
RUN apt-get update && apt-get install --no-install-recommends -y \
        ffmpeg \
        libsndfile1 \
        tini \
        git \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user; the app never needs root at runtime.
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# --- deps -------------------------------------------------------------------
# Copy the package first so pip picks up pyproject.toml before we invalidate
# the layer with source changes.
COPY --chown=app:app pyproject.toml README.md LISEZMOI.md LICENSE ./
COPY --chown=app:app podcast_helper ./podcast_helper

# Install with [api,mcp] extras so the container is ready to serve
# HTTP + MCP out of the box. `git` is kept in the image because our
# intra-family deps (youtube-helper, os-helper, audio-helper, …) are
# installed via git+https tags — pip needs `git` to resolve them.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir '.[api,mcp]'

# --- runtime ----------------------------------------------------------------
USER app
EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    PODCAST_HELPER_HOST=0.0.0.0 \
    PODCAST_HELPER_PORT=8000

# tini reaps orphan children (ffmpeg subprocesses) cleanly on SIGTERM.
ENTRYPOINT ["/usr/bin/tini", "--"]
# Default: serve FastAPI + MCP. Override for one-shot CLI usage.
CMD ["podcast-helper-mcp"]
