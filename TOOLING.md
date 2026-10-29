# Research, web & video tooling

Added 2026-10-28. Three toolkits, each wired in as an npm package, an MCP server for Claude Code, and/or agent skills.

| Tool | npm package(s) | MCP server (`.mcp.json`) | Skills (`skills/`) | Key |
|---|---|---|---|---|
| Playwright | `playwright`, `@playwright/test`, `@playwright/mcp` (dev) | `playwright` → `@playwright/mcp` | — | none |
| Firecrawl | `firecrawl` (SDK), `firecrawl-cli` (dev) | `firecrawl` → `firecrawl-mcp` | `firecrawl*` (32 skills) | `FIRECRAWL_API_KEY` |
| HyperFrames | `hyperframes` (HTML → MP4 CLI) | — | `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use` | optional `HEYGEN_API_KEY` |

## Setup on a machine (Antonelli-PC, Mac)

```bash
git pull
npm install
npx playwright install chromium        # browser binary, not committed
cp .env.example .env                   # if you don't have one yet
# add FIRECRAWL_API_KEY to .env
npm run check:tooling                  # smoke test — every line should say OK
```

Requirements: Node 22+ (HyperFrames needs it) and FFmpeg on PATH (HyperFrames renders with it).

Claude Code picks up `.mcp.json` automatically when opened in this repo (approve the two servers once). The `${FIRECRAWL_API_KEY}` placeholder is read from your shell environment, so export it (or set it as a Windows user env var) as well as putting them in `.env`.

Skills live canonically in `skills/` and are copied to `.claude/skills/` and `.cursor/skills/` by `shared/scripts/sync-skill.sh` (runs on every Claude Code session start). To refresh to newer upstream versions: `npx hyperframes skills update` and `npx firecrawl init -y --skip-install --skip-auth --agent claude-code`, then copy the updated folders from `~/.claude/skills/` into `skills/`.

## Quick use

```bash
npx hyperframes init my-video --non-interactive && cd my-video && npx hyperframes render
npx firecrawl scrape https://forgedbyfreedom.net
```

```js
import Firecrawl from 'firecrawl';
const doc = await new Firecrawl({ apiKey: process.env.FIRECRAWL_API_KEY }).scrape('https://example.com', { formats: ['markdown'] });
```

Perplexity was evaluated and skipped (2026-10-29): its API needs prepaid credit, and Claude/ChatGPT already cover that role.
