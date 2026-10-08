# OPENCODE.md

> Camada Harness (opencode, `BOOTSTRAP.md` §7.2). Segue, nesta ordem de precedência: [`AGENTS.md`](./AGENTS.md) (Constituição da plataforma de agentes), [`BOOTSTRAP.md`](./BOOTSTRAP.md) (estrutura e inicialização) e [`PROJECT.md`](./PROJECT.md) (regras deste repositório, agnósticas de harness). Este arquivo contém apenas o que é específico do opencode — não duplique aqui nada que já esteja em `AGENTS.md` ou `PROJECT.md`.

## Regras de Inicialização Obrigatórias (Startup Workflow)

Ao iniciar qualquer sessão ou antes de executar tarefas não-triviais, o opencode deve obrigatoriamente ler e carregar o contexto na seguinte ordem de autoridade descendente (`BOOTSTRAP.md` §5 e §7):

1. **`AGENTS.md`** — Constituição: leis globais, hierarquia de autoridade e precedência (§4), não duplicação e fonte de verdade (§5).
2. **`BOOTSTRAP.md`** — Estrutura, persistência (memória, journal, decisões), documentação padrão, inicialização e camadas de projeto/harness.
3. **`PROJECT.md`** — Regras técnicas do projeto, convenções de arquitetura, comandos e Single Source of Truth.
4. **`OPENCODE.md`** — Configurações específicas e workspace do opencode.
5. **`MEMORY.md`** — Estado durável atual, trabalho em andamento e convenções ativas.
6. **`.journal/`** — Consultar as últimas entradas em `.journal/YYYY/MM/DD/` quando for necessário reconstruir histórico de sessões anteriores.

---

## Repositório Canônico e Workspace

O repositório canônico de agentes, especialistas e skills é `.agents/` (link local para `harness-agent-platform`, fonte canônica de Agents e Skills — `BOOTSTRAP.md` §3 e §5). `.opencode/` é uma pasta local — o workspace individual do harness opencode neste projeto (`.<harness>/` em `BOOTSTRAP.md` §3), não um symlink para a plataforma; nenhum harness cria uma segunda hierarquia de agentes e Skills. Dentro dela, `.opencode/agents` e `.opencode/skills` são symlinks internos que apontam para `.agents/agents` e `.agents/skills`, para que o opencode encontre o conteúdo canônico no caminho que ele espera, sem duplicá-lo.

Sempre que a tarefa corresponder a um domínio existente, utilize os agentes e skills de `.agents/` (especialmente os agentes `opentelemetry*`, `grafanalabs-visualize` e `@mermaid-architecture`, e as skills `opentelemetry-*`, `grafanalabs-visualize-grafana-*` e `mermaid-render-diagram`) em vez de implementar do zero. As skills `grafanalabs-push-*`/`grafanalabs-pull-*` são baseadas em Grafana Alloy e não se aplicam mais a este repositório.
