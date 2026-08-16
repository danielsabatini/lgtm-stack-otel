# OPENCODE.md

> Camada Ferramenta (opencode). Segue, nesta ordem de precedência: [`AGENTS.md`](./AGENTS.md) (governança global da plataforma multiagente) e [`PROJECT.md`](./PROJECT.md) (regras deste repositório, agnósticas de ferramenta). Este arquivo contém apenas o que é específico do opencode — não duplique aqui nada que já esteja em `AGENTS.md` ou `PROJECT.md`.

O opencode lê `AGENTS.md` nativamente como seu formato de entrada — este arquivo existe apenas para completude da convenção `<FERRAMENTA>.md` (`AGENTS.md` §8.3) e como ponto de referência visível na raiz.

O repositório canônico de agentes, especialistas e skills é `.agents/` (symlink para `ai-agent-platform/.agents`, `AGENTS.md` §9). `.opencode/` é uma pasta local — o workspace individual da ferramenta opencode neste projeto (`AGENTS.md` §10), não um symlink para a plataforma. Dentro dela, `.opencode/agents` e `.opencode/skills` são symlinks internos que apontam para `.agents/agents` e `.agents/skills`, para que o opencode encontre o conteúdo canônico no caminho que ele espera, sem duplicá-lo.

Consulte [`MEMORY.md`](./MEMORY.md) para o estado de execução entre sessões antes de iniciar trabalho não-trivial.
