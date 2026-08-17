# CLAUDE.md

> Camada Ferramenta (Claude Code). Segue, nesta ordem de precedência: [`AGENTS.md`](./AGENTS.md) (governança global da plataforma multiagente) e [`PROJECT.md`](./PROJECT.md) (regras deste repositório, agnósticas de ferramenta). Este arquivo contém apenas o que é específico do Claude Code — não duplique aqui nada que já esteja em `AGENTS.md` ou `PROJECT.md`; se a regra valeria em qualquer ferramenta, ela pertence a `PROJECT.md` (teste de fronteira, `AGENTS.md` §8.4).

## Regras de Inicialização Obrigatórias (Startup Workflow)

Ao iniciar qualquer sessão ou antes de executar tarefas não-triviais, o Claude Code deve obrigatoriamente ler e carregar o contexto na seguinte ordem de autoridade descendente (`AGENTS.md` §2 e §8):

1. **`AGENTS.md`** — Leis globais, hierarquia de autoridade, DRY estrito e governança de agentes.
2. **`PROJECT.md`** — Regras técnicas do projeto, convenções de arquitetura, comandos e Single Source of Truth.
3. **`CLAUDE.md`** — Configurações específicas e adaptações da ferramenta.
4. **`MEMORY.md`** — Estado durável atual, trabalho em andamento e convenções ativas.
5. **`.journal/`** — Consultar as últimas entradas em `.journal/YYYY/MM/DD/` quando for necessário reconstruir histórico de sessões anteriores.

---

## Repositório Canônico e Agentes

Sempre que possível, carregue e utilize os agentes, subagentes e skills disponíveis em `.agents/` (symlink para o repositório canônico `ai-agent-platform/.agents`, `AGENTS.md` §9) em vez de reimplementar do zero — em particular o domínio `observability` (`agents/observability*.md`), `@mermaid-architecture` e as skills `skills/observability-*` (pull/push de métricas e logs, normalize, configure, visualize), que mapeiam diretamente os pipelines `.alloy` e o provisioning do Grafana deste repositório.
