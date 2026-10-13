# ADR 0001: Reorganização da documentação e adoção de `.agents/` canônico

> **Status:** Aceito
> **Data:** 2026-08-16 (registra retroativamente a decisão de 2026-08-13 e formaliza a decisão de 2026-08-16)

## 1. Contexto

Este repositório adota a governança multiagente definida em `AGENTS.md` (documento externo, symlink para `ai-agent-platform/AGENTS.md`, versão vigente 3.0). Duas decisões estruturais relevantes foram tomadas em sessões distintas:

1. Em 2026-08-13, toda a documentação temática da raiz (`ARCHITECTURE.md`, `INFRASTRUCTURE.md`, `SIZING.md`, `BACKUP.md`, `UPGRADE.md`, `METRICS.md`, `LOGS.md`, `TRACES.md`, `DASHBOARDS.md`, `ALERTS.md`, e por engano também `ROADMAP.md`) foi movida para `docs/`, e os artefatos não documentais `load-test/` e `scripts/` foram movidos para `artifacts/`.
2. Em 2026-08-16, uma auditoria de conformidade contra o `AGENTS.md` v3.0 (renumerado desde 2026-08-13) identificou que `ROADMAP.md` não podia estar em `docs/` — é um dos 5 arquivos padrão obrigatórios de raiz (`AGENTS.md` §11.1) — e que o repositório não possuía `.agents/` canônico (§9), usando apenas `.opencode` (symlink para a plataforma compartilhada `ai-agent-platform`).

## 2. Decisão

### 2.1 Documentação e artefatos

- Documentação temática (arquitetura, sizing, backup, upgrade, métricas, logs, traces, dashboards, alertas, metodologia) mora em `docs/`.
- Os 5 arquivos padrão de raiz exigidos por `AGENTS.md` §11.1 (`README.md`, `ROADMAP.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`) ficam exclusivamente na raiz — nenhum deles é tratado como "tema" equivalente aos arquivos de `docs/`.
- Artefatos não documentais reutilizáveis por outros agentes (scripts, dados de teste de carga, planilhas de referência) ficam em `artifacts/`.

### 2.2 Repositório canônico de agentes

- `.agents/` (symlink somente-leitura para `ai-agent-platform/.agents`) é o repositório canônico de agentes/skills deste projeto, conforme `AGENTS.md` §9.
- `.opencode/` é uma pasta local real — o workspace individual da ferramenta opencode neste projeto (`AGENTS.md` §10), não mais um symlink direto para `ai-agent-platform/.opencode`. Internamente, `.opencode/agents` e `.opencode/skills` são symlinks que apontam para `.agents/agents` e `.agents/skills`, para que o opencode encontre o conteúdo canônico no layout que a ferramenta espera, sem duplicá-lo fisicamente.
- Optou-se por symlink (para `.agents/`, e internamente dentro de `.opencode/`) em vez de duplicar arquivos de agentes/skills dentro deste repositório, para preservar DRY estrito (`AGENTS.md` §4) e o compartilhamento da plataforma entre múltiplos projetos-irmãos que dependem de `ai-agent-platform`.

## 3. Alternativas consideradas

- **Manter apenas `.opencode`, sem `.agents/` explícito**: rejeitada por não satisfazer a letra de `AGENTS.md` §9, que espera um `.agents/` canônico dentro do projeto consumidor.
- **Duplicar fisicamente agentes/skills em `.agents/` deste repositório**: rejeitada por violar DRY estrito e criar risco de drift entre este repositório e `ai-agent-platform`, que é a fonte real mantida.
- **Manter `.opencode` como symlink direto para `ai-agent-platform/.opencode`**: rejeitada a pedido do usuário — `.opencode` passou a ser uma pasta local real, mantendo apenas os symlinks internos `agents`/`skills` apontando para `.agents/`, para que o workspace da ferramenta opencode fique fisicamente dentro do projeto (`AGENTS.md` §10) em vez de ser, ele mesmo, um link externo.
- **Manter `ROADMAP.md` em `docs/` como os demais temas**: rejeitada porque contradiz diretamente `AGENTS.md` §11.1.2/§11.1.9, que classifica `ROADMAP.md` como arquivo padrão obrigatório de raiz, não documentação temática.

## 4. Consequências

- `README.md`, `PROJECT.md` e `docs/ALERTS.md` foram atualizados para linkar `ROADMAP.md` na raiz.
- `CLAUDE.md`, `OPENCODE.md`, `COPILOT.md` e `.github/copilot-instructions.md` foram atualizados para referenciar `.agents/` como fonte canônica e `.opencode/` como workspace local da ferramenta.
- `.gitignore` passou a ter dois blocos separados: um para os links compartilhados somente-leitura (`.agents`, `AGENTS.md`), outro para o workspace local `.opencode` (que, mesmo sendo pasta real, contém symlinks internos não portáveis entre máquinas/clones).
- Futuras adições de documentação temática devem ir para `docs/`; qualquer novo arquivo padrão de raiz deve seguir a lista fechada de `AGENTS.md` §11.1.

## 5. Referências

- `AGENTS.md` §9 (Repositório Canônico de Agentes), §11.1 (Documentação Padrão da Raiz), §4 (DRY Estrito).
- `.journal/2026/08/13/0001-bootstrap-governanca-camadas.md`
- `.journal/2026/08/16/0001-auditoria-conformidade-agents-v3.md`
- `CHANGELOG.md` — versão `0.0.14`.
