# CLAUDE.md

> Camada Harness (Claude Code, `BOOTSTRAP.md` §7.2). Segue, nesta ordem de precedência: [`AGENTS.md`](./AGENTS.md) (Constituição da plataforma de agentes), [`BOOTSTRAP.md`](./BOOTSTRAP.md) (estrutura e inicialização) e [`PROJECT.md`](./PROJECT.md) (regras deste repositório, agnósticas de harness). Este arquivo contém apenas o que é específico do Claude Code — não duplique aqui nada que já esteja em `AGENTS.md` ou `PROJECT.md`; se a regra valeria em qualquer harness, ela pertence a `PROJECT.md` (teste de fronteira, `BOOTSTRAP.md` §7.3).

## Regras de Inicialização Obrigatórias (Startup Workflow)

Ao iniciar qualquer sessão ou antes de executar tarefas não-triviais, o Claude Code deve obrigatoriamente ler e carregar o contexto na seguinte ordem de autoridade descendente (`BOOTSTRAP.md` §5 e §7):

1. **`AGENTS.md`** — Constituição: leis globais, hierarquia de autoridade e precedência (§4), não duplicação e fonte de verdade (§5).
2. **`BOOTSTRAP.md`** — Estrutura, persistência (memória, journal, decisões), documentação padrão, inicialização e camadas de projeto/harness.
3. **`PROJECT.md`** — Regras técnicas do projeto, convenções de arquitetura, comandos e Single Source of Truth.
4. **`CLAUDE.md`** — Configurações específicas e adaptações do Claude Code.
5. **`MEMORY.md`** — Estado durável atual, trabalho em andamento e convenções ativas.
6. **`.journal/`** — Consultar as últimas entradas em `.journal/YYYY/MM/DD/` quando for necessário reconstruir histórico de sessões anteriores.

---

## Repositório Canônico e Agentes

Sempre que possível, carregue e utilize os agentes, subagentes e skills disponíveis em `.agents/` (link local para o repositório canônico `harness-agent-platform`, fonte canônica de Agents e Skills — `BOOTSTRAP.md` §3 e §5) em vez de reimplementar do zero — em particular os agentes `opentelemetry*` (Collector, semconv, OTTL, eBPF/OBI, sampling), `grafanalabs-visualize` e `@mermaid-architecture`, e as skills `opentelemetry-*` (ex.: `opentelemetry-deploy-collector-agent-gateway`, `opentelemetry-apply-semantic-conventions`, `opentelemetry-instrument-ebpf-obi`, `opentelemetry-integrate-prometheus`, `opentelemetry-configure-tail-sampling`), `grafanalabs-visualize-grafana-*` e `mermaid-render-diagram`, que se aplicam às configs do OpenTelemetry Collector (`otel-gateway/`, `otel-agent/`, `examples/`) e ao provisioning do Grafana deste repositório. As skills `grafanalabs-push-*`/`grafanalabs-pull-*` são baseadas em Grafana Alloy e **não** se aplicam mais a este repositório.
