# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
