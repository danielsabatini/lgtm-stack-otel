# Copilot Instructions for lgtm-stack

> Harness layer (GitHub Copilot, `BOOTSTRAP.md` §7.2). Follows, in this order of precedence: [`AGENTS.md`](../AGENTS.md) (agent platform Constitution), [`BOOTSTRAP.md`](../BOOTSTRAP.md) (structure and initialization) and [`PROJECT.md`](../PROJECT.md) (this repository's rules, harness-agnostic). **Read them before making changes** — this file only contains what's specific to GitHub Copilot; everything else (architecture, commands, conventions) lives in `PROJECT.md` to avoid duplication (`BOOTSTRAP.md` §7.3 boundary test / `AGENTS.md` §5 single source of truth).

## Mandatory Startup Workflow

Before starting any task or making changes, Copilot must read and load context in the following strict order of descending authority (`BOOTSTRAP.md` §5 and §7):

1. **`AGENTS.md`** — Constitution: global laws, authority and precedence (§4), no duplication / single source of truth (§5).
2. **`BOOTSTRAP.md`** — Structure, persistence (memory, journal, decisions), standard docs, initialization and project/harness layers.
3. **`PROJECT.md`** — Repository technical rules, architecture conventions, commands, and Single Source of Truth.
4. **`.github/copilot-instructions.md`** — Harness-specific configuration.
5. **`MEMORY.md`** — Current durable state, active conventions, and cross-session memory.
6. **`.journal/`** — Check recent daily entries under `.journal/YYYY/MM/DD/` when historical execution context is required.

---

## Repository summary

Self-hosted observability stack (LGTM: Loki, Grafana, Tempo, Mimir) via Docker Compose. Not application code — declarative infrastructure (`compose.yaml`, backend YAML configs, OpenTelemetry Collector configs (`otel-gateway/`, `otel-agent/`, `examples/`), Grafana dashboard JSON) plus extensive PT-BR Markdown docs. Full architecture, commands, conventions, and doc-ownership table: see [`PROJECT.md`](../PROJECT.md).

## Copilot-specific notes

- Where applicable, use the agents/skills in `.agents/` (local link to the canonical `harness-agent-platform`, canonical source of Agents and Skills — `BOOTSTRAP.md` §3 and §5) instead of reimplementing from scratch — particularly the `opentelemetry*` agents and `opentelemetry-*` skills, `grafanalabs-visualize-grafana-*` and `mermaid-render-diagram`, which apply to this repo's OpenTelemetry Collector configs and Grafana provisioning. The `grafanalabs-push-*`/`grafanalabs-pull-*` skills are Grafana Alloy based and no longer apply.
- No test suite, linter, or build step exists in this repo — do not introduce one. Validation commands are listed in `PROJECT.md`.
- Documentation is Single Source of Truth (`PROJECT.md`): before editing any `.md`, identify the owning file and link to it instead of duplicating content.
