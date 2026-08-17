# PROJECT.md

> Regras deste repositório, agnósticas de ferramenta de IA (`AGENTS.md` §8.2). Conflito com `AGENTS.md` é resolvido a favor do `AGENTS.md` (§1). Regra de ferramenta específica (atalhos, permissões, configuração de cliente) não pertence aqui — vá para o `<FERRAMENTA>.md` correspondente.

## O que é este repositório

Stack de observabilidade (LGTM: Loki, Grafana, Tempo, Mimir) self-hosted via Docker Compose, voltada para deploy em VMs (principalmente Magalu Cloud). Não é código de aplicação — é infraestrutura declarativa: `compose.yaml`, configs YAML dos backends, pipelines Alloy (`.alloy`), dashboards JSON do Grafana e documentação extensa em Markdown (PT-BR).

## Governança de documentação (regra crítica)

Este repositório segue **Single Source of Truth** estrito (ver `CONTRIBUTING.md`): cada `.md` de documentação técnica é a única fonte de verdade sobre seu tema — é proibido duplicar informação técnica entre arquivos, sempre referencie via link. Na raiz ficam apenas os 5 arquivos padrão exigidos por `AGENTS.md` §11.1 (`README.md`, `ROADMAP.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`) mais `AGENTS.md`, `PROJECT.md`, `MEMORY.md` e os `<FERRAMENTA>.md`; toda a documentação temática (não-padrão) mora em `docs/`. Antes de editar algo, identifique o documento dono do assunto:

| Arquivo | Tema |
|---|---|
| `docs/ARCHITECTURE.md` | Topologia, papéis dos componentes, fronteiras de rede, portas |
| `docs/INFRASTRUCTURE.md` | Setup físico, disco (LVM), volumes, permissões |
| `docs/SIZING.md` | Dimensionamento, cardinalidade, projeção de custo/disco |
| `docs/BACKUP.md` | Backup, snapshot, disaster recovery |
| `docs/UPGRADE.md` | Processo de upgrade de versões e breaking changes dos TSDBs |
| `docs/METRICS.md` | Política de métricas, labels, descrições padronizadas e retenção no Mimir |
| `docs/LOGS.md` | Política de logs, labels e retenção no Loki |
| `docs/TRACES.md` | Ingestão OTLP e tail sampling no Tempo |
| `docs/DASHBOARDS.md` | Fluxo de edição/conversão/provisioning de dashboards |
| `docs/OBSERVABILITY-METHODOLOGY.md` | Metodologia de observabilidade, taxonomia de pilares, correlação de sinais (M/L/T), SLIs/SLOs e playbook |
| `docs/ALERTS.md` | Status/placeholder da estratégia de alertas |
| `ROADMAP.md` (raiz) | Visão de futuro e próximas funcionalidades — arquivo padrão de raiz (`AGENTS.md` §11.1.2), não fica em `docs/` |
| `CHANGELOG.md` | Histórico de versões |

### Padrão Estrutural e de Linguagem das Documentações (Mandatório)

Toda documentação em `docs/` deve seguir rigorosamente o padrão abaixo:

1. **Estrutura Padronizada e Numerada:**
   * Iniciar com `## 1. Introdução` contextualizando o problema/tema.
   * Seguir com `## 2. Objetivo` estabelecendo metas claras e mensuráveis.
   * Subdivisões numeradas em ordem hierárquica (`## 3...`, `### 3.1`, `### 3.2`...).
   * Concluir com a seção de Governança e links cruzados.
2. **Linguagem Simples, Direta e Acessível:**
   * O objetivo é que **qualquer operador, suporte ou desenvolvedor (mesmo júnior ou sem conhecimento prévio profundo da ferramenta)** compreenda imediatamente o texto e saiba como agir.
   * Evitar jargões técnicos isolados sem explicação prática.
   * Sempre incluir comandos reais de verificação (`journalctl`, `systemctl`, `ping`, `dig`, `curl`) e passos de mitigação concretos.

Regra prática: se alterar rede → atualize `docs/ARCHITECTURE.md`; se alterar métricas → atualize `docs/METRICS.md` e `docs/SIZING.md`; toda mudança relevante deve ser seguida de atualização imediata da documentação pertinente, incluindo `CHANGELOG.md`.

## Comandos comuns

```bash
cp .env.example .env              # configurar antes do primeiro up
docker compose up -d              # subir a stack
docker compose down               # parar (mantém dados)
docker compose down -v            # reset completo — apaga todos os volumes
docker compose ps                 # status dos containers
docker compose logs -f            # logs em tempo real (ou logs -f loki mimir tempo grafana)
docker compose config --quiet     # valida sintaxe do compose.yaml + .env antes de qualquer pull/upgrade
docker compose pull               # baixa novas imagens (usar antes de subir upgrade)
```

Healthchecks manuais (Loki, Mimir e Tempo são distroless, sem shell — não usar `docker exec`):

```bash
curl -s http://localhost:3000/api/health | jq .database   # Grafana
curl -s http://localhost:12345/-/ready                     # Alloy Gateway
```

Validação de config de um TSDB antes de subir upgrade (troque a versão pela do `.env`):

```bash
docker run --rm -v $(pwd)/loki/loki.yaml:/etc/loki/local-config.yaml \
  grafana/loki:<versao> -config.file=/etc/loki/local-config.yaml -verify-config
```

Não existe test suite, linter ou build step neste repositório — validação é feita via `docker compose config`, `-verify-config` dos binários, e checagem manual de ingestão pós-deploy (ver checklist em `docs/UPGRADE.md`).

**Ao criar ou editar qualquer arquivo `.alloy` em `examples/`**, rode antes de finalizar:

```bash
python3 artifacts/scripts/check-examples-consistency.py
```

Esse script (a) valida a sintaxe de todo `.alloy` em `examples/` contra a imagem `grafana/alloy` pinada em `.env.example` (requer Docker), (b) confere se os arquivos que enviam dados ao gateway carregam os 5 labels de identidade global (`instance`, `environment`, `cloud_provider`, `cloud_region`, `cloud_availability_zone`), e (c) compara a allowlist de métricas entre arquivos que o próprio repositório documenta como espelhos um do outro (ex.: `linux/config.alloy` ↔ `pull-linux-hosts.alloy`; `windows/config.alloy` ↔ `windows-mssql/config.alloy` ↔ `pull-windows-*-hosts.alloy`). Os templates em `examples/` são single-file por design (facilita copiar para um host remoto), então essa duplicação é proposital — o script existe para pegar o caso em que uma métrica ou label é atualizado em um arquivo e esquecido nos espelhos.

## Arquitetura (visão essencial)

**Padrão Gateway-Agent**: o Alloy é dividido em dois papéis para não expor um processo root à rede:

- **Alloy Agent** (`alloy-agent/`): roda `privileged: true`/root, lê `/procfs`, `/sys`, `/rootfs`, journald e Docker socket para coletar métricas/logs do host. Não expõe portas na rede. Envia tudo via push HTTP interno para o Gateway.
- **Alloy Gateway** (`alloy-gateway/`): roda sem privilégios, é o único ponto de ingestão da stack (OTLP 4317/4318, Loki push 9998, Prometheus remote_write 9999). Faz fanout para Loki, Mimir e Tempo.

**Regra arquitetural inviolável**: todo `prometheus.remote_write` (agente local, agentes remotos, pull legado) deve apontar para `http://alloy-gateway:9999/api/v1/metrics/write`. Nunca escrever diretamente em `mimir:9009`.

Loki, Mimir e Tempo não publicam portas no host — só acessíveis pela rede Docker `lgtm`, e são imagens distroless (sem shell, sem healthcheck `CMD-SHELL`). Grafana é o único ponto de leitura.

**Política de métricas Lean (whitelist estrita)**: em vez de coletar tudo que os exporters (Node Exporter, cAdvisor, mysqld_exporter, postgres_exporter) produzem, cada pipeline `.alloy` aplica `metric_relabel` com ação `keep` para reter só o que os dashboards usam — reduz cardinalidade em 80–95%. Nunca adicione uma métrica "por segurança". Ao adicionar um painel novo que precise de métrica ainda não coletada: adicione a métrica na regra `keep` do `.alloy` correspondente (`alloy-agent/conf.d/` para push local, `alloy-gateway/conf.d/pull-*.alloy` para pull remoto) e, se a cardinalidade subir de forma relevante, atualize `docs/SIZING.md`.

**Convenção de arquivos `.alloy`** (`alloy-agent/conf.d/`, `alloy-gateway/conf.d/`): nome no padrão `<numero>-<tipo>-<categoria>-<serviço>.alloy` (ex.: `200-log-sec-ssh.alloy`, `001-metric-node-local.alloy`). O número controla ordem de carregamento. Pipelines de log seguem 4 estágios encadeados via `forward_to`, com componentes nomeados `<serviço>_<passo>`:

1. `loki.source.journal` (SOURCE) — filtra por `_SYSTEMD_UNIT`
2. `loki.relabel` (TRANSFORM) — normaliza `priority` → `level`, injeta labels estáticos (`category`, `service_name`)
3. `loki.process` (NORMALIZE) — dropa por priority, aplica labels finais
4. `loki.write` (WRITE) — envia para `alloy-gateway`

Hosts são identificados apenas pelo label `instance` (nunca `nodename`, para evitar cardinalidade duplicada). Use variáveis do Grafana (`$instance`, `$container`) em vez de nomes de host fixos.

**Dashboards** (`grafana/provisioning/dashboards/` — Fonte Única da Verdade): todos os dashboards são armazenados exclusivamente sob o schema de recursos nativos do Grafana 13 (`dashboard.grafana.app/v2`). Fluxo GitOps: edite na UI do Grafana → exporte diretamente via API nativa v2 (`GET /apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>`) → salve no arquivo correspondente em `grafana/provisioning/dashboards/<Pasta>/<nome>.json` → commit. Nunca use o endpoint legado `/api/dashboards/db` (que destrói `TabsLayout` achatando em linhas simples). UIDs de dashboards em produção nunca devem mudar. `grafana/provisioning/dashboards/dashboards.yaml` faz hot-reload a cada 10s. Detalhes completos e padrões de design em `docs/DASHBOARDS.md`.

**`examples/`**: modelos de monitoramento divididos em duas categorias: `examples/push/` (templates de agentes locais com seu próprio `INSTALL.md` e `config.alloy` para serem instalados dentro do host alvo) e `examples/pull/` (templates de scraping remoto para serem carregados no `alloy-gateway/conf.d/` da stack central).

## Convenções de versão e upgrade

Todas as versões de imagem são parametrizadas no `.env` com fallback seguro no `compose.yaml` (ex.: `${GRAFANA_LOKI_VERSION:-3.7.1}`) — nunca usar `:latest`. Loki, Mimir e Tempo (TSDBs) não podem pular major versions — migração sequencial obrigatória; o Grafana pode pular majors com segurança. Antes de qualquer bump de versão de TSDB, ler as release notes procurando `schema_config`/`Breaking Changes`/`migration` (detalhes e breaking changes conhecidos em `docs/UPGRADE.md`).

Os três arquivos de config (`loki/loki.yaml`, `mimir/mimir.yaml`, `tempo/tempo.yaml`) já contêm workarounds para requisitos não óbvios das respectivas engines (ex.: `ruler_storage`/`ruler.rule_path` obrigatórios no Mimir mesmo sem regras, `compactor.delete_request_store` obrigatório no Loki quando há retenção, `block_retention`/`compaction_window` dentro de `compactor.compaction` no Tempo) — não remover essas seções ao editar.

## Princípios de design (de `CONTRIBUTING.md`)

1. **Whitelist first** — nunca adicione uma métrica "por segurança"; só o que os dashboards exigem.
2. **Desacoplamento** — Alloy Agent coleta (privilegiado), Alloy Gateway ingere (sem privilégios).
3. **Portabilidade** — use variáveis do Grafana (`$instance`, `$container`), não nomes de host fixos.
4. **Sincronização de alertas** — thresholds visuais nos painéis só existem para métricas com alertas, com valores idênticos aos da regra de alerta.
5. **Fluxo GitOps (Local First → Sync Remoto)** — Toda alteração de configuração, dashboards ou pipelines deve ser realizada e versionada primeiro no repositório local (Fonte Única da Verdade) e então sincronizada para os servidores remotos (via rsync/SSH/API). É proibido alterar arquivos diretamente em produção sem persistir no repositório.

## Idioma

Documentação técnica deste repositório é escrita em PT-BR.
