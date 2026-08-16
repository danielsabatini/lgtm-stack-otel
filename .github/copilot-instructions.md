# Copilot Instructions for lgtm-stack

> Tool layer (GitHub Copilot). Follows, in this order of precedence: [`AGENTS.md`](../AGENTS.md) (global multi-agent platform governance) and [`PROJECT.md`](../PROJECT.md) (this repository's rules, tool-agnostic). **Read both before making changes** — this file only contains what's specific to GitHub Copilot; everything else (architecture, commands, conventions) lives in `PROJECT.md` to avoid duplication (`AGENTS.md` §8.4 boundary test / §4 strict DRY).

## Mandatory Startup Workflow

Before starting any task or making changes, Copilot must read and load context in the following strict order of descending authority (`AGENTS.md` §2 and §8):

1. **`AGENTS.md`** — Global platform laws, descending authority, strict DRY, and security rules.
2. **`PROJECT.md`** — Repository technical rules, architecture conventions, commands, and Single Source of Truth.
3. **`.github/copilot-instructions.md`** — Tool-specific configuration.
4. **`MEMORY.md`** — Current durable state, active conventions, and cross-session memory.
5. **`.journal/`** — Check recent daily entries under `.journal/YYYY/MM/DD/` when historical execution context is required.

---

## Repository summary

Self-hosted observability stack (LGTM: Loki, Grafana, Tempo, Mimir) via Docker Compose. Not application code — declarative infrastructure (`compose.yaml`, backend YAML configs, Alloy `.alloy` pipelines, Grafana dashboard JSON) plus extensive PT-BR Markdown docs. Full architecture, commands, conventions, and doc-ownership table: see [`PROJECT.md`](../PROJECT.md).

## Copilot-specific notes

- Where applicable, use the agents/skills in `.agents/` (symlink to the canonical `ai-agent-platform/.agents`, `AGENTS.md` §9) instead of reimplementing from scratch — particularly the `observability` domain and `observability-*` skills, which map directly to this repo's `.alloy` pipelines and Grafana provisioning.
- No test suite, linter, or build step exists in this repo — do not introduce one. Validation commands are listed in `PROJECT.md`.
- Documentation is Single Source of Truth (`PROJECT.md`): before editing any `.md`, identify the owning file and link to it instead of duplicating content.
