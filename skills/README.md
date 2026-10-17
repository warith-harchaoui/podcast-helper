# podcast-helper as an agent skill

`skills/podcast-helper/` packages `podcast-helper` as a **Claude Skill** *and* an **OpenCode
skill** — both ecosystems read the same `SKILL.md` (YAML frontmatter + Markdown
body + progressive-disclosure `references/`). Installing it lets an agent
discover podcast-helper and read RSS feeds, probe episodes, and stream or record their audio on the user's behalf, without the user opening a
terminal.

## Layout

```
skills/podcast-helper/
├── SKILL.md                  # name + trigger-rich description + instructions
└── references/
    ├── cli-reference.md      # full subcommand + flag matrix, output contract
    ├── surfaces.md           # library, two CLIs, HTTP API, MCP, and the browser GUI
    └── triggers.md           # exhaustive, auditable trigger catalogue
```

Progressive disclosure, as the published skill standard prescribes: the YAML
frontmatter is always in the host model's context, `SKILL.md`'s body loads only
when the skill looks relevant, and `references/*.md` load only when a task
actually needs that depth. The `description` stays under the 1024-character cap;
the exhaustive trigger list lives in `references/triggers.md`.

## Install for Claude Code / Claude Desktop

Skills live under `~/.claude/skills/` (user) or `.claude/skills/` (project). To
track this repo's copy rather than duplicate it, symlink it:

```bash
ln -sfn "$PWD/skills/podcast-helper" ~/.claude/skills/podcast-helper
# per-project instead:
mkdir -p /path/to/project/.claude/skills
ln -sfn "$PWD/skills/podcast-helper" /path/to/project/.claude/skills/podcast-helper
```

## Install for OpenCode

OpenCode reads skills from `~/.opencode/skills/` (or `~/.config/opencode/skills/`):

```bash
mkdir -p ~/.opencode/skills
ln -sfn "$PWD/skills/podcast-helper" ~/.opencode/skills/podcast-helper
```

## Keeping triggers enforced

The host model only sees `SKILL.md`'s `description` before deciding to load the
skill, so every real trigger must be represented there — compressed into the
1024-character budget. `references/triggers.md` is the human-reviewable
superset, and it mirrors the repo-root `TRIGGERS.md` (the user-facing catalogue). When one changes, change the other.

This helper is network-bound by definition — fetching a feed or an episode is
its job. It reads public RSS and media URLs and writes to local paths; there is
no account, no telemetry, no third-party relay.
