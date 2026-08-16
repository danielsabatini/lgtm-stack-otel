# CLAUDE.md

> Camada Ferramenta (Claude Code). Segue, nesta ordem de precedência: [`AGENTS.md`](./AGENTS.md) (governança global da plataforma multiagente) e [`PROJECT.md`](./PROJECT.md) (regras deste repositório, agnósticas de ferramenta). Este arquivo contém apenas o que é específico do Claude Code — não duplique aqui nada que já esteja em `AGENTS.md` ou `PROJECT.md`; se a regra valeria em qualquer ferramenta, ela pertence a `PROJECT.md` (teste de fronteira, `AGENTS.md` §8.4).

Sempre que possível, carregue e utilize os agentes, subagentes e skills disponíveis em `.agents/` (symlink para o repositório canônico `ai-agent-platform/.agents`, `AGENTS.md` §9) em vez de reimplementar do zero — em particular o domínio `observability` (`agents/observability*.md`) e as skills `skills/observability-*` (pull/push de métricas e logs, normalize, configure, visualize), que mapeiam diretamente os pipelines `.alloy` e o provisioning do Grafana deste repositório.

Consulte [`MEMORY.md`](./MEMORY.md) para o estado de execução entre sessões (pendências, convenções ativas) antes de iniciar trabalho não-trivial.
