# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
