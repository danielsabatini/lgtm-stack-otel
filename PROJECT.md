# PROJECT.md

> Regras deste repositório, agnósticas de ferramenta de IA (`AGENTS.md` §8.2). Conflito com `AGENTS.md` é resolvido a favor do `AGENTS.md` (§1). Regra de ferramenta específica (atalhos, permissões, configuração de cliente) não pertence aqui — vá para o `<FERRAMENTA>.md` correspondente.

## O que é este repositório

Stack de observabilidade (LGTM: Loki, Grafana, Tempo, Mimir) self-hosted via Docker Compose, voltada para deploy em VMs (principalmente Magalu Cloud). Não é código de aplicação — é infraestrutura declarativa: `compose.yaml`, configs YAML dos backends e do OpenTelemetry Collector (gateway e agents), templates `.alloy` legados em migração, dashboards JSON do Grafana e documentação extensa em Markdown (PT-BR).

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
curl -s http://localhost:13133/                            # OTel Gateway (health_check)
```

Validação de config de um TSDB antes de subir upgrade (troque a versão pela do `.env`):

```bash
docker run --rm -v $(pwd)/loki/loki.yaml:/etc/loki/local-config.yaml \
  grafana/loki:<versao> -config.file=/etc/loki/local-config.yaml -verify-config
```

Não existe test suite, linter ou build step neste repositório — validação é feita via `docker compose config`, `-verify-config` dos binários, e checagem manual de ingestão pós-deploy (ver checklist em `docs/UPGRADE.md`).

**Ao criar ou editar qualquer template em `examples/`** (config do OpenTelemetry Collector ou `.alloy` legado), rode antes de finalizar:

```bash
python3 artifacts/scripts/check-examples-consistency.py
```

Esse script (requer Docker) (a) valida toda config do OpenTelemetry Collector em `examples/` (YAML com bloco `receivers:`) com `otelcol-contrib validate` na versão pinada em `.env.example` (`OTELCOL_CONTRIB_VERSION`), (b) confere nelas a identidade OpenTelemetry (`resource_detection` com detectores `env` + `system` e `override: true`, saída para `${env:LGTM_GATEWAY_ENDPOINT}`), e, para os templates `.alloy` ainda não migrados, (c) valida a sintaxe com `grafana/alloy`, (d) confere os 5 labels de identidade legados e (e) compara as allowlists entre arquivos espelhados. Os templates em `examples/` são single-file por design (facilita copiar para um host remoto), então a duplicação é proposital — o script pega o caso em que algo é atualizado num arquivo e esquecido nos espelhos.

## Arquitetura (visão essencial)

**Padrão Gateway-Agent com OpenTelemetry Collector**: a coleta (privilegiada, no host) é separada da ingestão (sem privilégios, exposta na rede):

- **Agent** (`examples/push/<sistema>/`): **OpenTelemetry Collector Contrib** (`otelcol-contrib`, pacote oficial) instalado no host monitorado — métricas de host (`host_metrics`), logs (`journald`, Windows Event Log), receivers nativos de bancos — mais o **OBI** (OpenTelemetry eBPF Instrumentation, serviço `obi` opcional) para traces e métricas HTTP sem alterar código. O OBI envia OTLP ao Collector local (`127.0.0.1:4317`); o Collector aplica a identidade do host e é a única saída para o Gateway. Não expõe portas na rede.
- **Gateway** (`otel-gateway/config.yaml`, serviço `otel-gateway` no `compose.yaml`): `otelcol-contrib` em container, sem privilégios, único ponto de ingestão da stack, **somente OTLP** (4317 gRPC / 4318 HTTP). Não converte nem renomeia dados — só aplica `memory_limiter`, `tail_sampling` (traces) e `batch` — e grava em OTLP nativo: métricas → Mimir, logs → Loki, traces → Tempo. Health check em `:13133`.

- **Agent da própria stack** (`otel-agent/`, serviço `otel-agent` no `compose.yaml`): o mesmo Collector em container, com `network_mode: host`, `pid: host`, root sem capabilities (`cap_drop: ALL`) e mounts somente leitura; coleta host, containers (`docker_stats` + logs `json-file`) e journald do servidor da stack.

> **Migração em andamento:** os templates `.alloy` de `examples/` (exceto `push/linux`) ainda usam o Grafana Alloy com `remote_write`/Loki push e **não entregam dados** ao Gateway OTLP até serem migrados (ver `ROADMAP.md`).

**Regras arquiteturais invioláveis**:
1. **Só o Gateway escreve nos backends.** Nenhum agente, aplicação ou backend escreve direto em `mimir:9009`, `loki:3100` ou `tempo:4317`.
2. **Cada backend armazena apenas o seu sinal**: métricas no Mimir, logs no Loki, traces no Tempo (por isso o `metrics_generator` do Tempo é desabilitado; métricas RED vêm do OBI na origem).
3. **O dado sai da origem já correto**: agents e aplicações enviam OTLP com nomes e atributos da [OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/). Conversões (ex.: exporter Prometheus → OTLP) acontecem no agente, nunca no Gateway.
4. **Identidade única por host**: definida uma vez no agente (`OTEL_RESOURCE_ATTRIBUTES` + detector `system`, `override: true`) — `host.name`, `deployment.environment.name`, `cloud.provider`, `cloud.region`, `cloud.availability_zone`. Nunca labels de identidade fixos por pipeline.

Loki, Mimir e Tempo não publicam portas no host — só acessíveis pela rede Docker `lgtm`, e são imagens distroless (sem shell, sem healthcheck `CMD-SHELL`). Grafana é o único ponto de leitura.

**Política Lean (coletar e armazenar o mínimo necessário)**: nada é coletado "por segurança". Nas configs do Collector, cada scraper/métrica (`metrics: <nome>: { enabled: true|false }`) e cada fonte de log (com filtro de severidade na origem, ex.: `priority: warning` no journald) é explícita; dispositivos, filesystems e interfaces sem valor operacional são excluídos; o self-monitoring usa `level: basic`; o OBI exporta só `features: [application]`. Nos templates `.alloy` legados, a mesma política é aplicada com `metric_relabel` `keep`. Ao precisar de uma métrica nova para um painel, habilite-a explicitamente no template correspondente e, se a cardinalidade subir de forma relevante, atualize `docs/SIZING.md`.

**Nomes no Mimir e no Loki**: métricas são gravadas com os nomes OpenTelemetry (PromQL com aspas: `{"system.cpu.time", "host.name"="web-01"}`); no Loki os resource attributes de identidade viram labels com `_` (`host_name`, `service_name`). Use variáveis do Grafana (`$host`, `$service`) em vez de nomes fixos. Detalhes em `docs/METRICS.md` e `docs/LOGS.md`.

**Dashboards** (`grafana/provisioning/dashboards/` — Fonte Única da Verdade): todos os dashboards são armazenados exclusivamente sob o schema de recursos nativos do Grafana 13 (`dashboard.grafana.app/v2`). Fluxo GitOps: edite na UI do Grafana → exporte diretamente via API nativa v2 (`GET /apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>`) → salve no arquivo correspondente em `grafana/provisioning/dashboards/<Pasta>/<nome>.json` → commit. Nunca use o endpoint legado `/api/dashboards/db` (que destrói `TabsLayout` achatando em linhas simples). UIDs de dashboards em produção nunca devem mudar. `grafana/provisioning/dashboards/dashboards.yaml` faz hot-reload a cada 10s. Detalhes completos e padrões de design em `docs/DASHBOARDS.md`. Os dashboards atuais ainda consultam os nomes Prometheus antigos e serão refeitos sobre os nomes OpenTelemetry.

**`examples/`**: modelos de monitoramento em duas categorias: `examples/push/` (agentes instalados no host alvo, cada um com seu `INSTALL.md` e configs) e `examples/pull/` (coletas remotas de servidores **sem agente**, ex.: só `node_exporter`). Os templates pull são copiados para `otel-agent/pull.d/` (não versionado) e executados pelo `otel-agent` da stack, que faz o scrape, converte para OTLP com a identidade OpenTelemetry declarada por alvo e envia ao Gateway — o Gateway nunca executa coletas. O pipeline pull não usa `resource_detection` (atribuiria a identidade da stack). Templates pull ainda em `.alloy` estão em migração.

## Convenções de versão e upgrade

Todas as versões de imagem são parametrizadas no `.env` com fallback seguro no `compose.yaml` (ex.: `${GRAFANA_LOKI_VERSION:-3.7.1}`) — nunca usar `:latest`. Loki, Mimir e Tempo (TSDBs) não podem pular major versions — migração sequencial obrigatória; o Grafana pode pular majors com segurança. Antes de qualquer bump de versão de TSDB, ler as release notes procurando `schema_config`/`Breaking Changes`/`migration` (detalhes e breaking changes conhecidos em `docs/UPGRADE.md`).

Os três arquivos de config (`loki/loki.yaml`, `mimir/mimir.yaml`, `tempo/tempo.yaml`) já contêm workarounds para requisitos não óbvios das respectivas engines (ex.: `ruler_storage`/`ruler.rule_path` obrigatórios no Mimir mesmo sem regras, `compactor.delete_request_store` obrigatório no Loki quando há retenção, `block_retention`/`compaction_window` dentro de `compactor.compaction` no Tempo) — não remover essas seções ao editar.

## Princípios de design (de `CONTRIBUTING.md`)

1. **Whitelist first** — nunca adicione uma métrica "por segurança"; só o que os dashboards exigem.
2. **Desacoplamento** — o agente coleta (privilegiado, no host), o Gateway ingere (sem privilégios, somente OTLP).
3. **Portabilidade** — use variáveis do Grafana (`$instance`, `$container`), não nomes de host fixos.
4. **Sincronização de alertas** — thresholds visuais nos painéis só existem para métricas com alertas, com valores idênticos aos da regra de alerta.
5. **Fluxo GitOps (Local First → Sync Remoto)** — Toda alteração de configuração, dashboards ou pipelines deve ser realizada e versionada primeiro no repositório local (Fonte Única da Verdade) e então sincronizada para os servidores remotos (via rsync/SSH/API). É proibido alterar arquivos diretamente em produção sem persistir no repositório.

## Idioma

Documentação técnica deste repositório é escrita em PT-BR.
