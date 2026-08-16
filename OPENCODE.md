# OPENCODE.md

> Camada Ferramenta (opencode). Segue, nesta ordem de precedência: [`AGENTS.md`](./AGENTS.md) (governança global da plataforma multiagente) e [`PROJECT.md`](./PROJECT.md) (regras deste repositório, agnósticas de ferramenta). Este arquivo contém apenas o que é específico do opencode — não duplique aqui nada que já esteja em `AGENTS.md` ou `PROJECT.md`.

## Regras de Inicialização Obrigatórias (Startup Workflow)

Ao iniciar qualquer sessão ou antes de executar tarefas não-triviais, o opencode deve obrigatoriamente ler e carregar o contexto na seguinte ordem de autoridade descendente (`AGENTS.md` §2 e §8):

1. **`AGENTS.md`** — Leis globais, hierarquia de autoridade, DRY estrito e governança de agentes.
2. **`PROJECT.md`** — Regras técnicas do projeto, convenções de arquitetura, comandos e Single Source of Truth.
3. **`OPENCODE.md`** — Configurações específicas e workspace da ferramenta.
4. **`MEMORY.md`** — Estado durável atual, trabalho em andamento e convenções ativas.
5. **`.journal/`** — Consultar as últimas entradas em `.journal/YYYY/MM/DD/` quando for necessário reconstruir histórico de sessões anteriores.

---

## Repositório Canônico e Workspace

O repositório canônico de agentes, especialistas e skills é `.agents/` (symlink para `ai-agent-platform/.agents`, `AGENTS.md` §9). `.opencode/` é uma pasta local — o workspace individual da ferramenta opencode neste projeto (`AGENTS.md` §10), não um symlink para a plataforma. Dentro dela, `.opencode/agents` e `.opencode/skills` são symlinks internos que apontam para `.agents/agents` e `.agents/skills`, para que o opencode encontre o conteúdo canônico no caminho que ele espera, sem duplicá-lo.

Sempre que a tarefa corresponder a um domínio existente, utilize os agentes e skills de `.agents/` (especialmente `@observability`, `@mermaid-architecture`, etc.) em vez de implementar do zero.
