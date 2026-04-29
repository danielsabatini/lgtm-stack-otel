# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
