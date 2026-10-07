# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Alterado
- **Grafana Alloy substituído pelo OpenTelemetry Collector + OBI** — *breaking change*:
  - **Gateway:** `alloy-gateway/` → `otel-gateway/config.yaml` (OpenTelemetry
    Collector Contrib `0.162.0`, imagem oficial): OTLP 4317/4318 →
    `memory_limiter` → `tail_sampling` → `batch` → OTLP nativo no Mimir, Loki e
    Tempo. Health check em `:13133` (substitui a UI `:12345`); self-monitoring
    (`level: basic`) em OTLP para a própria entrada.
  - **Agent da stack:** `alloy-agent/` → `otel-agent/` (Collector em container
    com `journalctl`): `host_metrics` (`system.*`), `docker_stats`
    (`container.*`), journald (ssh, kernel, docker, containerd, cron, systemd)
    e logs dos containers via `json-file`. `network_mode: host`, `pid: host`,
    root sem capabilities (`cap_drop: ALL`, `no-new-privileges`) e mounts
    somente leitura — antes `privileged: true` com `/var/run` gravável.
  - **Agent Linux** (`examples/push/linux`): `otelcol-contrib` (pacote oficial)
    + **OBI** `v0.14.0` (OpenTelemetry eBPF Instrumentation, substitui o Beyla)
    com `obi.service` próprio (usuário `obi`, capabilities eBPF). Métricas HTTP
    com nomes da OTel Semantic Conventions (`http.server.request.duration`),
    sobre 100% do tráfego, com exemplars `trace_id`; propagação de contexto W3C
    validada (frontend → middleware → backend sob um único `traceID`).
  - **Identidade única por host:** `OTEL_RESOURCE_ATTRIBUTES` + detector
    `system` com `override: true` (`host.name`, `deployment.environment.name`,
    `cloud.*`) — o OBI usa FQDN e passaria a divergir sem o override.
  - **Política Lean explícita:** cada métrica (`enabled: true|false`) e cada
    fonte de log é listada; severidade filtrada na origem; ~66 séries por host
    Linux (antes ~356 com `node_exporter`). `check-examples-consistency.py`
    valida configs do Collector e o espelhamento da política entre o template
    de host e o `otel-agent`.
  - **Compose:** logs de todos os serviços em `json-file` com rotação
    (`x-logging`); novas variáveis `OTELCOL_CONTRIB_VERSION`, `OBI_VERSION`,
    `OTEL_GATEWAY_*`, `OTEL_AGENT_*`.
  - **Mimir:** `container.name` e `container.image.name` promovidos a label —
    sem eles as séries `container.*` de containers diferentes se misturavam.
  - Validado em VM Debian 13 (kernel 6.12): journald, host metrics, OBI,
    Docker em container e queda de 70 s do Gateway sem perda de amostras.
- **`examples/pull/linux-dbaas-pgsql` migrado**: scrape de `/node/metrics` e
  `/postgres/metrics` (proxy :8080 do DBaaS) pelo `otel-agent`, jobs
  `node-exporter`/`postgres-exporter`, identidade por instância,
  `db.system.name=postgresql` e `datname` → `db.namespace` (mesma dimensão do
  template push). Descartados `template0`/`template1` e o label `server`:
  44 séries de banco contra 597 expostas. Validado contra DBaaS PostgreSQL
  16.11: `xact_commit` e `database_size` idênticos à origem.
- **`examples/pull/linux-dbaas-mysql` migrado**: scrape de `/node/metrics` e
  `/mysql/metrics` (proxy :8080 do DBaaS) pelo `otel-agent`, jobs
  `node-exporter`/`mysqld-exporter`, identidade OpenTelemetry por instância e
  `db.system.name=mysql` no resource do banco. Allowlist de SO alinhada à do
  pull Linux; 14 métricas `mysql_*` (16 séries com `up`) contra ~3.000
  expostas. Validado contra DBaaS MySQL 8.4.6 via bastion (túnel SSH).
- **Coleta pull de servidores legados pelo `otel-agent`** (`examples/pull/linux`):
  o scrape de `node_exporter` remotos sai do Gateway e passa ao `otel-agent`,
  que carrega `otel-agent/pull.d/*.yaml` (novo `entrypoint.sh`; arquivos com
  IPs do ambiente não versionados). Converte para OTLP com a identidade
  OpenTelemetry declarada por alvo (sem `resource_detection`), mantém os nomes
  `node_*` e a allowlist Lean (64 séries por servidor contra ~1.555 expostas;
  `scrape_*` descartadas). O Gateway continua só OTLP. O `INSTALL.md` exige
  restringir a `:9100` do servidor legado ao IP da stack. O
  `check-examples-consistency.py` valida cada template pull mesclado com o
  `otel-agent/config.yaml`.
- **`examples/push/linux-pgsql` migrado para OpenTelemetry Collector**: host
  (mesma base do template Linux) + receiver nativo `postgresql` com o feature
  gate `receiver.postgresql.useOTelSemconv` (um resource por servidor e banco
  em `db.namespace`; sem ele as séries de bancos diferentes se misturavam no
  Mimir) e só métricas no nível de banco (~14 séries por banco; as por
  tabela/índice, ligadas por padrão, desligadas) + log do PostgreSQL com
  agrupamento de `DETAIL`/`HINT`/`CONTEXT`/`STATEMENT`, fuso `-03`/`UTC`
  normalizado e filtro `WARN`+ preservando slow queries. Validado com
  PostgreSQL 18.6 (PGDG): commits, rollbacks, deadlocks e tuplas batem com o
  `pg_stat_database`; deadlock real chega como um único registro `ERROR`.
- **`examples/push/linux-mysql` migrado para OpenTelemetry Collector**: host
  (mesma base do template Linux, conferida pelo script de consistência) +
  receiver nativo `mysql` (~38 séries, lista explícita; desligadas as
  `table/index.io.wait.*`, que vêm ligadas por padrão com uma série por
  tabela/índice) + error log (`file_log`, severidade OTel, `mysql.error.code`).
  Usuário de monitoramento com privilégios mínimos e credencial no arquivo de
  ambiente com modo `640`. Validado com MySQL Community 8.4.11 LTS: slow
  queries, row lock waits e queries batem com o `global_status` da fonte.
- **Bump de versões da stack** (primeiro passo da migração para OTLP nativo
  fim-a-fim): Grafana `13.1.2` → `13.2.3`, Alloy `v1.18.0` → `v1.20.1`,
  Loki `3.7.4` → `3.7.8`, Mimir `3.1.4` → `3.2.1`, Tempo `3.0.2` → `3.1.0`
  (`.env.example`, `compose.yaml`). Configs validadas contra as novas imagens
  (`-verify-config` no Loki, `-modules` no Mimir, startup do Tempo,
  `alloy validate` no gateway, agent e todos os `examples/`). Breaking changes
  avaliados em `docs/UPGRADE.md` §3.1 — nenhum afeta esta stack; Tempo passa a
  gravar blocos novos em vParquet5 sem migração.
- **Monolito single-tenant explícito**: `target: all` adicionado em
  `loki/loki.yaml` e `tempo/tempo.yaml`, e `multitenancy_enabled: false` em
  `tempo/tempo.yaml` (antes implícitos por default). Regra registrada em
  `docs/UPGRADE.md` §3 (Regra 3).

- **Data-root do Docker parametrizado**: os binds fixos `/var/lib/docker` e
  `/docker` do `alloy-agent` (cAdvisor) foram substituídos por um único
  `${DOCKER_DATA_ROOT}` montado no mesmo caminho do host (`.env.example`,
  default `/docker`; fallback `/var/lib/docker` no `compose.yaml`). Permite
  subir a stack em hosts sem o disco dedicado `/docker` (ex.: Docker Desktop).

- **Backends e Gateway 100% OTLP (migração OpenTelemetry)** — *breaking change*:
  - Alloy Gateway aceita **somente OTLP** (4317/4318) e grava em OTLP nativo no
    Mimir (`/otlp/v1/metrics`), Loki (`/otlp/v1/logs`) e Tempo, sem conversões:
    removidas as pontes `otelcol.exporter.prometheus`/`otelcol.exporter.loki`,
    os writers `prometheus.remote_write`/`loki.write`, as portas 9998/9999
    (`compose.yaml`) e os arquivos `000-metric-alloy-local.alloy`,
    `001-metric-gtw-local.alloy` e `002-log-gtw-local.alloy`.
  - Mimir: semântica OpenTelemetry preservada (`NoTranslation` + nomes UTF-8,
    native histograms, promoção dos resource attributes de identidade,
    exemplars habilitados). Loki: `host.name` e `cloud.provider` como index
    labels; `trace_id`/`span_id`/`severity_text` em structured metadata.
  - Tempo: `metrics_generator` desabilitado — cada backend guarda só o seu
    sinal; RED e Service Graph passam a vir do Beyla nos agents.
  - Regras arquiteturais revistas em `PROJECT.md` e `docs/ARCHITECTURE.md`:
    só o Gateway escreve nos backends; dado sai correto da origem.
  - **Impacto:** Alloy Agents e templates de `examples/` (ainda em
    `remote_write`/Loki push para 9999/9998) param de entregar dados até a
    migração dos clientes; dashboards serão refeitos sobre os nomes OTel.
- `ROADMAP.md`: removido o item "Multi-tenancy" — toda instalação é
  monolítica e single-tenant (`docs/UPGRADE.md` §3, Regra 3).

### Corrigido
- `MEMORY.md`: a heurística "`sampling_traces_on_memory` ==
  `new_trace_id_received` indica tail sampling travado" estava errada — os
  traces permanecem em memória após a decisão, então os valores coincidem em
  operação normal. O sinal correto é `global_count_traces_sampled` parado com
  spans chegando.
- `dockerd`/`containerd` gravam todos os logs no journal com `PRIORITY=6`;
  o filtro por prioridade descartava os erros (`level=error`). Agora o nível
  é extraído do texto.
- **Exemplars**: estavam descartados pelo Mimir (`max_global_exemplars_per_user: 0`).
- **Link Trace → Métricas** removido do datasource Tempo: apontava para
  `traces_spanmetrics_duration_milliseconds_bucket` (inexistente) e as métricas
  do Tempo foram desligadas; será refeito sobre as métricas do Beyla.
- **Links Log ↔ Trace para logs OTLP**: derived field por label `trace_id`
  (structured metadata) e query Trace → Logs `| trace_id="..."`; regex legado mantido.
- **UI do Alloy Agent**: escutava só em `127.0.0.1` dentro do container, então a
  porta publicada não respondia. Agora `--server.http.listen-addr=0.0.0.0:12345`,
  publicada apenas em `127.0.0.1:12346` no host (agent root não expõe portas na rede).
- `docs/UPGRADE.md`: dry-run do Tempo usava `-version` (não valida a config);
  substituído por subida de container descartável. Dry-run do Loki passa a
  injetar `LOKI_RETENTION`, e foi incluída a validação dos pipelines Alloy.

## [0.0.15] - 2026-08-16
### Adicionado
- **Solução Completa MGC Internal DNS** (`grafana/provisioning/dashboards/DNS/mgc-internal-dns.json` - UID: `adth4vt`): monitoramento em 3 camadas interdependentes (*Linux, CoreDNS e etcd*) com SLIs de latência interna (<16ms) e forward (<250ms), Upstream Health, Process RSS, Cache Evictions e Cluster Role (Leader/Follower).
- **Diagramas Mermaid Vetoriais** (`docs/diagrams/`): geração local e automatizada de diagramas em SVG e PNG de alta resolução para topologia de rede (`docs/ARCHITECTURE.md`) e fluxo de avaliação de alertas (`docs/ALERTS.md`) via `@mermaid-architecture` e `mermaid-render-diagram`.
- **Separação Arquitetural de Cache**: visualização macro no pilar *Capacity* (consumo acumulado vs. teto físico de 110 K) e visualização micro cirúrgica no pilar *Diagnostics* dividida em 2 gráficos dedicados (*Válidos* com escala de 50 K e *NXDOMAIN* com escala de 5 K).
- **Padronização Visual Unificada de Capacidade**: fundo branco limpo, linhas de uso suaves e tetos máximos/limites em linhas tracejadas vermelhas no topo em todos os 7 dashboards da stack.

### Alterado
- **Dashboard Linux Hosts** (`grafana/provisioning/dashboards/Hosts/linux-hosts.json`): convertido para seleção única de host (`single-select`) com legendas limpas sem prefixo redundante de instância e cards de inventário centralizados (`textMode: "value"`).
- **Efeito Center Glow**: habilitado em todos os gráficos do tipo Gauge em todos os dashboards da stack.
- **Gerador de Carga DNS** (`artifacts/load-test/dns-load-test.sh`): otimizado com tráfego realista corporativo (60% etcd, 20% saída legítima, 5% NXDOMAIN) e expansão do pool de domínios.

### Corrigido
- **Eliminação de Falsos Alarmes**: painéis `Query Rate` e `Upstream Health` configurados com mapeamento neutro cinza (`sem tráfego` / `#6E7B8B`) na ausência de requisições, eliminando cards vermelhos quando o ambiente está ocioso.
- **Unificação GitOps de Dashboards**: remoção definitiva da pasta obsoleta `grafana-dashboards-backup/` e de recursos clonados no Grafana 13, estabelecendo `grafana/provisioning/dashboards/` como fonte única da verdade.

## [0.0.14] - 2026-08-13
### Adicionado
- **`docs/OBSERVABILITY-METHODOLOGY.md`**: nova referência única conceitual e
  metodológica para a taxonomia de pilares (Health, Capacity, Activity,
  Diagnostics, Inventory, Logs, Traces), correlação de sinais (Métricas, Logs,
  Traces via Exemplars/TraceID), gestão de confiabilidade com SLIs/SLOs/Error
  Budgets, governança de cardinalidade Lean e playbook de incidentes em 4 fases.
- **`.agents/`**: link simbólico canônico (somente leitura, mesmo padrão de
  `AGENTS.md`) para o repositório compartilhado `ai-agent-platform/.agents`,
  alinhando este projeto ao `AGENTS.md` §9 (`.agents/` como repositório
  canônico de agentes/skills).

### Alterado
- **Reorganização da documentação**: a documentação temática não-padrão
  (`ARCHITECTURE.md`, `INFRASTRUCTURE.md`, `SIZING.md`, `BACKUP.md`,
  `UPGRADE.md`, `METRICS.md`, `LOGS.md`, `TRACES.md`, `DASHBOARDS.md`,
  `ALERTS.md`) foi movida da raiz para `docs/`. `ROADMAP.md` permanece
  (e retorna, após correção de conformidade — ver abaixo) na raiz: é um
  dos 5 arquivos padrão exigidos por `AGENTS.md` §11.1
  (`README.md`/`ROADMAP.md`/`CHANGELOG.md`/`CONTRIBUTING.md`/`LICENSE`),
  não documentação temática. A raiz do repositório agora contém os 5
  arquivos padrão mais `AGENTS.md`, `PROJECT.md`, `MEMORY.md` e os
  `<FERRAMENTA>.md` (`CLAUDE.md`, `OPENCODE.md`, `COPILOT.md`).
  `CLAUDE.md`/`OPENCODE.md`/`COPILOT.md` permanecem na raiz
  propositalmente — são arquivos de configuração de ferramenta, não
  documentação de produto. Todos os links cruzados entre documentos
  (`README.md`, `CONTRIBUTING.md`, `load-test/LOAD-TEST.md`, e entre os
  próprios docs movidos) foram atualizados para o novo caminho.
- **Reorganização de artefatos não-documentais**: `load-test/` e
  `scripts/` foram movidos para `artifacts/load-test/` e
  `artifacts/scripts/`. A planilha de referência de métricas do CoreDNS
  passou a viver em `artifacts/sheets/`. Referências em
  `CONTRIBUTING.md`, `docs/BACKUP.md` e
  `examples/remote-scrape/INSTALL.md` foram atualizadas para os novos
  caminhos.

### Corrigido
- **Duplicação de `ROADMAP.md`**: a reorganização de documentação acima
  havia movido `ROADMAP.md` para `docs/`, mas um novo `ROADMAP.md` na
  raiz chegou a ser criado em paralelo sem remover o de `docs/`,
  deixando duas fontes de verdade divergentes. Consolidado em
  `ROADMAP.md` (raiz, conteúdo mais atual) por ser um dos 5 arquivos
  padrão obrigatórios de raiz (`AGENTS.md` §11.1.2/§11.1.9);
  `docs/ROADMAP.md` foi removido e todos os links (`README.md`,
  `PROJECT.md`, `docs/ALERTS.md`) apontam agora para a raiz.
- **Referências de seção obsoletas ao `AGENTS.md`**: `MEMORY.md`,
  `CLAUDE.md`, `OPENCODE.md`, `COPILOT.md`,
  `.github/copilot-instructions.md`, `PROJECT.md` e `.gitignore` citavam
  números de seção do `AGENTS.md` (`§6.1`, `§6.3`, `§7.7`, `§13`,
  `§16.1`, `§17`) que não correspondem mais à numeração atual (v3.0).
  Todas as referências foram corrigidas para as seções vigentes.
- **`.opencode` deixou de ser symlink**: passou a ser uma pasta local real
  (workspace individual da ferramenta opencode, `AGENTS.md` §10), com
  `.opencode/agents` e `.opencode/skills` como symlinks internos para
  `.agents/agents` e `.agents/skills` — preserva o funcionamento do
  opencode sem apontar a pasta inteira para fora do projeto.

## [0.0.13] - 2026-08-04
### Alterado
- **Stack completa atualizada para as últimas versões estáveis**: Loki
  `3.7.1` → `3.7.4`, Alloy `v1.16.0` → `v1.18.0`, Tempo `2.10.5` → `3.0.2`
  (major version). Validado com `docker compose down -v` + subida limpa de
  todos os serviços, mais teste end-to-end real (Beyla eBPF em host remoto
  → Alloy Gateway → tail sampling → Tempo 3.0.2 → métricas RED no Mimir):
  tail sampling idêntico ao anterior (1 trace `keep-slow`, 3 traces
  `keep-errors`), `traces_spanmetrics_calls_total` populando, agente
  remoto reconectou automaticamente.
- `tempo/tempo.yaml`: migrado para a estrutura 3.0 — blocos `ingester` e
  `compactor` removidos; retenção/compactação movida para
  `backend_scheduler.provider.compaction.compaction.block_retention` e
  `backend_worker.compaction.block_retention` (configurados nos dois
  lugares com o mesmo valor de `${TEMPO_RETENTION}`, confirmado via
  `/status/config` do binário real). Modo monolítico sem Kafka, sem
  componentes novos.
- `UPGRADE.md`: novo apêndice "Tempo 2.x → 3.x" documentando o processo
  real de migração (descoberto por tentativa/erro contra o binário 3.0.2,
  já que a documentação oficial não tinha exemplo de YAML completo) e o
  aviso de que não há caminho de downgrade de 3.0 para 2.x.

## [0.0.12] - 2026-08-04
### Alterado
- Mimir atualizado `3.0.6` → `3.1.4` (corrige múltiplos CVEs de Go/dependências:
  CVE-2026-39822, CVE-2026-42505, CVE-2026-39833, CVE-2026-39882, CVE-2026-2303).
  Nenhuma flag removida na 3.1 (`-distributor.metric-relabeling-enabled`,
  `-querier.response-streaming-enabled`, etc.) está em uso em `mimir.yaml`.
- Validado com reset completo do ambiente (`docker compose down -v` + subida
  limpa): todos os 6 dashboards provisionados carregam, os 3 datasources
  (Mimir/Loki/Tempo) saudáveis, e um Alloy Agent remoto (host de teste real)
  reconectou automaticamente sem reconfiguração.

### Corrigido
- `UPGRADE.md`: os 3 comandos de "Validação a Seco" (Loki/Mimir/Tempo)
  nunca funcionavam — faltava `-config.expand-env=true`, então o parser
  sempre falhava com `not a valid duration string: "${...}"` mesmo em
  configs válidas (falso negativo). Todos os `.yaml` desses TSDBs usam
  variáveis de ambiente (`${MIMIR_RETENTION}` etc.) e o `compose.yaml`
  já roda com essa flag — só faltava no comando documentado.
- `UPGRADE.md`: checklist de "Leitura de Histórico" não alertava que a
  checagem só é conclusiva com blocos já compactados no storage — dados
  recém-ingeridos ficam no WAL/ingester e não exercitam mudanças de
  formato de bloco/índice entre versões de TSDB. Nota adicionada com
  comando para verificar blocos existentes antes de confiar no teste.

### Observado (não bloqueante)
- Grafana 13.1.2 loga `[SHOULD NOT HAPPEN] failed to update managedFields`
  ao carregar `linux-pgsql-hosts.json` (campos do schema v2 não reconhecidos
  no tracking interno de managedFields). O dashboard carrega normalmente
  (58 painéis, confirmado via API) — não afeta os outros 5 dashboards.
  Não investigado a fundo; registrar aqui para acompanhar em upgrades futuros.

## [0.0.11] - 2026-08-04
### Alterado
- Grafana atualizado `13.0.1` → `13.1.2` (corrige CVE-2026-13438). Confirmado
  que a stack não usa nenhum dos recursos removidos na 13.1.0 (auth Azure/
  sigv4 no datasource Prometheus nativo, plugin Zipkin) — `datasources.yaml`
  usa apenas `prometheus`/`loki`/`tempo` sem auth especial. Upgrade validado
  na prática: migração SQLite limpa (5 migrações executadas, 0 erros novos),
  healthcheck OK, ingestão de métricas/logs confirmada via API.

### Corrigido
- `UPGRADE.md`: item do checklist `{container="alloy-gateway"}` nunca
  retornava dados — o label `container` não existe no schema de labels
  deste projeto (é `service_name`). Substituído por `{service_name="ssh"}`.
- `UPGRADE.md`: adicionadas notas sobre (a) upgrade só do Grafana não exigir
  parar a stack inteira (SQLite local, sem WAL compartilhado com TSDBs),
  (b) `docker compose pull` sem argumento baixar imagens que não mudaram,
  (c) a imagem do Grafana não ter um modo verify-config/dry-run como os
  TSDBs — o entrypoint sempre inicia o servidor completo.
- `UPGRADE.md`: Matriz de Compatibilidade atualizada com Grafana 13.1.2.

## [0.0.10] - 2026-08-04
### Adicionado
- Seção opcional de Traces via Beyla eBPF em `examples/linux/config.alloy`
  (`beyla.ebpf` → `otelcol.processor.transform` → `otelcol.processor.batch`
  → `otelcol.exporter.otlp`), com sampler `always_on` delegando o corte de
  volume ao tail sampling já existente no Alloy Gateway. Configuração
  validada com `alloy validate` contra a imagem `grafana/alloy:v1.16.0`.
- Guia de pré-requisitos, capabilities eBPF (drop-in systemd) e
  troubleshooting em `examples/linux/INSTALL.md`, seção
  "Traces (Beyla eBPF) — Opcional".
- Nova seção em `TRACES.md` documentando o escopo de coleta remota via
  Beyla (Linux apenas; não aplicável a DBaaS gerenciado nem ao modelo pull).
- Nota de cardinalidade de `traces_spanmetrics_*` em `SIZING.md`.

### Corrigido
- **Crítico** — `tempo/tempo.yaml`: o receiver OTLP (`distributor.receivers.otlp.protocols`) não
  declarava `endpoint`, e o Tempo 2.10.5 usa por padrão `127.0.0.1` (loopback) em vez de `0.0.0.0`
  para esse caso — o Alloy Gateway nunca conseguia alcançar `tempo:4317`/`tempo:4318` pela rede
  Docker (`connection refused`). Isso bloqueava **qualquer** ingestão de traces na stack, não
  apenas Beyla. Corrigido declarando `endpoint: 0.0.0.0:4317`/`0.0.0.0:4318` explicitamente.
  Encontrado e validado em teste end-to-end real (Beyla eBPF em host Debian 13 remoto → Alloy
  Gateway → tail sampling → Tempo → Grafana), confirmado via `otelcol_exporter_sent_spans_total`
  e busca de traces na API do Tempo.
- `examples/linux/INSTALL.md`: capability `CAP_SYS_ADMIN` adicionada ao drop-in systemd do
  Beyla — não documentada oficialmente, mas necessária em teste real (Debian 13, kernel 6.12)
  para o `discover.ProcessWatcher` (sem ela, o Beyla só detecta processos já em execução antes
  do Alloy iniciar).
- `examples/linux/INSTALL.md`: seção "Verificar o envio de dados" instruía procurar as
  mensagens de log `"Writing metrics"`/`"Successfully flushed"`, que não existem na versão
  atual do Alloy (`v1.16.0` fica em silêncio em envios bem-sucedidos, só loga em `WARN` nas
  falhas) — substituído por consulta direta à API do Mimir/Loki. Nome do dashboard citado
  corrigido de "Node Exporter Linux (Remote)" (inexistente) para "Linux Hosts" (título real
  do provisioning).
- `examples/linux/INSTALL.md` e `examples/remote-scrape/INSTALL.md`: comandos de verificação
  via `docker exec grafana curl ... | jq` nunca funcionaram — a imagem oficial do Grafana não
  inclui `jq`. Removido o pipe, com nota explicando o que procurar no JSON bruto retornado.
- `examples/linux/config.alloy`: blocos `rule { ... }` com múltiplos
  atributos compactados em uma única linha (seções LOGS e GLOBAL LABELS)
  não passavam em `alloy validate` — reformatados para um atributo por
  linha, sem alteração de comportamento.
- `examples/windows/config.alloy`: arquivo estava truncado (faltavam as
  seções de Logs Security/System/Application/Platform, Global Identity e
  Outputs anunciadas no próprio cabeçalho) — o Alloy nunca conseguia
  iniciar com esse arquivo. Reconstruído a partir do padrão já validado
  em `examples/windows-mssql/config.alloy`.
- `examples/linux-mysql/config.alloy` e `examples/linux-pgsql/config.alloy`:
  endpoint do gateway usava `alloy-gateway.meudominio.internal` em vez do
  padrão `lgtm-stack`; nenhum label de identidade (`instance`,
  `environment`, `cloud_provider`, `cloud_region`, `cloud_availability_zone`)
  era injetado, causando colisão de `instance` (`__address__` bruto) entre
  múltiplos hosts monitorados pelo mesmo template.
- Referências de caminho quebradas em `examples/remote-scrape/pull-windows-mssql-hosts.alloy`
  (apontava para `examples/mssql/` inexistente) e `pull-linux-hosts.alloy`
  (apontava para arquivos numerados dentro de `examples/linux/`, que na
  verdade vivem em `alloy-agent/conf.d/`).
- Todos os `.alloy` de `examples/` validados com `alloy validate` contra
  `grafana/alloy:v1.16.0`.
- `examples/linux-mysql/config.alloy` e `examples/linux-pgsql/config.alloy`:
  credenciais de banco (`data_source_name`/`data_source_names`) estavam
  hardcoded no arquivo — externalizadas via `sys.env("MYSQL_EXPORTER_DSN")`/
  `sys.env("POSTGRES_EXPORTER_DSN")`, mesmo padrão usado no resto do repo
  para valores sensíveis/variáveis. Adicionada seção "Alloy Self" (ausente
  nesses dois templates) para monitorar a saúde do próprio agente.
- Removida entrada duplicada `windows_system_boot_time_timestamp` na
  allowlist de métricas Windows, presente em 4 arquivos
  (`examples/windows/config.alloy`, `examples/windows-mssql/config.alloy`,
  `examples/remote-scrape/pull-windows-hosts.alloy`,
  `examples/remote-scrape/pull-windows-mssql-hosts.alloy`).

### Alterado
- Identidade global de traces (`instance`, `environment`, `cloud_provider`,
  `cloud_region`, `cloud_availability_zone`) padronizada com os mesmos
  nomes e valores já usados nos pipelines de métricas e logs, garantindo
  correlação por label entre os 3 sinais no Grafana Explore.

### Corrigido (pós-merge com a série 0.0.9)
- `examples/remote-scrape/pull-linux-hosts.alloy`: referência
  `pull_linux_host_host_info` (nome duplicado, bug já presente desde a
  renomeação de componentes da versão 0.0.9) apontava para um componente
  inexistente (`pull_linux_host_info`) — pego pelo
  `scripts/check-examples-consistency.py` ao revalidar após o merge.

## [0.0.9] - 2026-05-04
### Alterado
- Auditoria 1:1 e implementação de *Strict Whitelisting* nos templates Alloy (`pull-linux-dbaas-mysql-hosts.alloy`, `pull-linux-dbaas-pgsql-hosts.alloy` e `001-metric-node-local.alloy`), restringindo o envio ao Mimir de forma exata às métricas consumidas nos dashboards.
- Padronização de nomenclatura de componentes em todos os templates Alloy (prefixo `pull_` implementado para blocos `scrape`, `relabel` e `remote_write`).
- Revisão completa e precisão aumentada no dimensionamento de armazenamento de métricas documentado no `SIZING.md` (v1.5).

## [0.0.8] - 2026-05-04
### Adicionado
- Seção "Passo Zero: Teste de Conectividade" no guia de instalação de coleta remota, priorizando a validação de rede via `curl`/`wget`.
- Nota operacional no `INSTALL.md` para transferência de templates via `scp` em ambientes com restrição ao Git.
- Instruções detalhadas nos cabeçalhos de todos os templates de coleta remota sobre a substituição de placeholders.

### Alterado
- Generalização de todos os templates em `examples/remote-scrape/`, substituindo IPs e nomes de instância fixos por marcadores genéricos `[IP_ADDRESS]` e `[INSTANCE_NAME]`.
- Reescrita do guia `INSTALL.md` para uma linguagem técnica mais profissional e acessível.
- Padronização das labels de infraestrutura (`environment`, `cloud_provider`, `cloud_region`, `cloud_availability_zone`) com avisos sobre valores padrão do Magalu Cloud (MGC).

## [0.0.7] - 2026-05-04
### Alterado
- Otimização rigorosa do *explicit whitelisting* (keep) nos arquivos `pull-linux-dbaas-mysql-hosts.alloy` e `pull-linux-dbaas-pgsql-hosts.alloy`, restringindo as métricas apenas àquelas efetivamente utilizadas nos dashboards do Grafana.
- Redução massiva do footprint ativo: MySQL caiu para ~73 séries (redução de 95%) e PostgreSQL caiu para ~128 séries (redução de 90%).
- `SIZING.md` atualizado com as novas volumetrias, reduzindo a projeção de custo de armazenamento de métricas.

## [0.0.6] - 2026-04-30
### Corrigido
- Dashboard `linux-mysql-hosts.json`: removido label `datname` inexistente nas métricas do `mysqld_exporter`, corrigindo painéis sem dados em Activity, Capacity e Diagnostics.
- Dashboard `linux-mysql-hosts.json`: removidos painéis `Connections by Database` (id=50) e `Query Latency` (id=59) com expressões semanticamente incorretas.
- Dashboard `linux-mysql-hosts.json` e `linux-pgsql-hosts.json`: removido `panel-59` (Query Latency) sem implementação válida.
- Dashboards MySQL e PostgreSQL: variável `$instance` corrigida para usar `mysql_up` e `pg_up` respectivamente (em vez de `node_uname_info`).

### Adicionado
- Provisioning automático dos dashboards `linux-mysql-hosts.json` e `linux-pgsql-hosts.json` via `grafana/provisioning/dashboards/`.
- `DASHBOARDS.md` reescrito documentando o processo de conversão do formato de export do Grafana 13 para provisioning (envelope `apiVersion/kind/metadata/spec`).
- `SIZING.md` v1.3: auditoria real de cardinalidade via Mimir — MySQL (302 séries), PostgreSQL (186 séries), com tabela comparativa e fórmulas de projeção.

### Alterado
- `ARCHITECTURE.md`: portas do Alloy Gateway detalhadas (4317 gRPC, 4318 HTTP, 9998 Loki, 9999 Prometheus remote_write).
- `SIZING.md`: números baseados em dados reais do Mimir, substituindo estimativas anteriores. Alerta sobre `mysql_global_status_commands_total` (168 séries = 82% do total MySQL).

## [0.0.5] - 2026-04-30
### Adicionado
- Nova configuração de coleta remota (Pull) para monitoramento de **DBaaS MySQL** (`pull-linux-dbaas-mysql-hosts.alloy`).
- Dashboard Grafana pré-configurado para MySQL (`linux-mysql-hosts.json`) com suporte a todos os 6+2 Pilares.
- Suporte a métricas equivalentes entre PostgreSQL e MySQL com filtros granulares nos templates Alloy.
- Guia de referência de dashboards (`DASHBOARDS.md`) centralizando templates disponíveis.
- Filtros granulares (whitelisting) para 43 métricas MySQL InnoDB, otimizando disco e cardinalidade.

### Alterado
- README.md atualizado para indicar MySQL disponível via coleta pull no Q2 2026.
- INSTALL.md expandido com seção "Linux + DBaaS MySQL" com instruções de configuração e paths dos exporters.

## [0.0.4] - 2026-04-28
### Adicionado
- Nova configuração de coleta remota (Pull) para monitoramento de **DBaaS PostgreSQL** (`pull-linux-dbaas-pgsql-hosts.alloy`).
- Instruções atualizadas no guia de instalação `INSTALL.md` para suportar o mapeamento customizado de portas e paths em proxies de banco de dados.
- Filtros rigorosos (whitelisting) para métricas do Postgres, otimizando o consumo de disco e reduzindo cardinalidade.

## [0.0.3] - 2026-04-25
### Adicionado
- Coleta de métricas de memória (`container_memory_usage_bytes`) no Alloy Agent.
- Coleta de métricas de períodos de CPU (`container_cpu_cfs_periods_total`) para detecção de throttling.
- Auditoria de sizing atualizada no `SIZING.md` refletindo o novo volume de métricas.

### Alterado
- Imagens atualizadas:
    - Grafana Alloy para `v1.16.0`.
    - Grafana Mimir para `3.0.6`.
    - Grafana Tempo para `2.10.5`.

## [0.0.2] - 2026-04-24
### Adicionado
- Implementação do modelo **Lean Observability**.
- Filtros de **Explicit Whitelisting (keep)** em todos os coletores Alloy.
- Redução de mais de 80% na cardinalidade de métricas para Linux, Windows e MSSQL.
- Arquitetura desacoplada: **Alloy Agent** (Host/Root) e **Alloy Gateway** (Ingestão/Unprivileged).
- Documentação de governança: `ARCHITECTURE.md`, `METRICS.md`, `SIZING.md`.

## [0.0.1] - 2026-04-10
### Adicionado
- Lançamento inicial da Stack LGTM unificada via Docker Compose.
- Provisionamento automático de Datasources (Loki, Mimir, Tempo).
- Provisionamento de Dashboards base para infraestrutura e containers.
- Suporte a logs via Docker discovery e Journald.
