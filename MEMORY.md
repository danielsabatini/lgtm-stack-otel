# MEMORY.md

> Índice da memória de execução, compartilhado entre ferramentas de IA neste repositório (`AGENTS.md` §13). Entradas completas ficam em `.journal/` (histórico local, não comitado — não atravessa clone/máquina). Este índice tem teto de tamanho: entradas antigas saem daqui e permanecem só no journal.

## Estado durável

- **Em andamento:** nenhum.
- **Bloqueado:** nenhum.
- **Convenções ativas:** ver `PROJECT.md` (regras técnicas) e `AGENTS.md` (governança da plataforma). `.agents/` (symlink somente-leitura para `ai-agent-platform/.agents`) é o repositório canônico de agentes/skills (`AGENTS.md` §9). `.opencode/` é uma pasta local real (workspace da ferramenta opencode, `AGENTS.md` §10) com `.opencode/agents` e `.opencode/skills` symlinkados internamente para `.agents/agents` e `.agents/skills`.
- **Pendência de processo:** a partir desta sessão, toda tarefa que altere estado permanente do repositório deve gerar uma entrada em `.journal/` (`AGENTS.md` §14.5/§14.13) — o gap de 2026-08-13 a 2026-08-16 (upgrades de Grafana/Mimir/Loki/Alloy/Tempo, rollout de monitoramento DNS) não tem entradas correspondentes e não é reconstruível retroativamente.

## Entradas recentes

- **2026-08-16 — Auditoria de conformidade com `AGENTS.md` v3.0** (`.journal/2026/08/16/0001-auditoria-conformidade-agents-v3.md`): consolidação de `ROADMAP.md` (removida duplicação raiz/`docs/`), correção de referências de seção obsoletas do `AGENTS.md` em `MEMORY.md`/`CLAUDE.md`/`OPENCODE.md`/`COPILOT.md`/`.github/copilot-instructions.md`/`PROJECT.md`/`.gitignore`, criação do symlink canônico `.agents/` (decisão do usuário: criar `.agents/` local em vez de depender só de `.opencode`), troca de `.opencode` de symlink externo para pasta local real com symlinks internos `agents`/`skills` apontando para `.agents/` (decisão do usuário, mesma sessão), redação de credencial em texto puro em `.claude/settings.local.json`, reestruturação de `.journal/` para o padrão `YYYY/MM/DD/NNNN-slug.md`, e ADR em `docs/decisions/` registrando as decisões de 2026-08-13 e 2026-08-16.
- **2026-08-13 — Bootstrap de governança em camadas** (`.journal/2026/08/13/0001-bootstrap-governanca-camadas.md`): criação de `PROJECT.md`, enxugamento de `CLAUDE.md`/`OPENCODE.md`/`.github/copilot-instructions.md`, stub `COPILOT.md`, criação deste `MEMORY.md` e do `.journal/`.
