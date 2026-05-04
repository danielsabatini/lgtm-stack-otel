# Dimensionamento e Estudo de Capacidade (Sizing)

Este documento contém os resultados da auditoria de capacidade e as projeções de consumo de hardware para a stack LGTM em modo **Lean Observability**.

## 1. Resumo dos Resultados (Abril/2026)

Após a implementação da política de **Explicit Whitelisting (keep)**, a cardinalidade foi reduzida em mais de 90% em comparação com os exporters padrão.

| Categoria | Séries Ativas (Mimir) | Redução vs. Padrão |
|---|---|---|
| **Linux Host** | ~98 | **77%** |
| **Windows Host** | ~30 a 50 | **90%** |
| **Windows + MSSQL** | ~45 a 65 | **92%** |
| **Containers (cAdvisor)** | ~8 | **84%** |
| **Linux + DBaaS PostgreSQL** | ~128 (60 node + 68 pg) | **90%** |
| **Linux + DBaaS MySQL** | ~73 (60 node + 13 mysql) | **95%** |

## 2. Consumo Estimado por Host

Valores baseados em auditoria real do **Mimir** (retenção de **30 dias**, scrape interval de **30s**, overhead TSDB de **2.5x**):

| Tipo de Host | Séries Ativas | Mimir (Métricas) | Loki (Logs) | Total/mês |
|---|---|---|---|---|
| **Linux Host** (node-exporter) | ~98 | ~26 MB | ~50-250 MB | ~100-300 MB |
| **Linux + DBaaS PostgreSQL** | ~128 | ~35 MB | ~50-250 MB | ~85-285 MB |
| **Linux + DBaaS MySQL** | ~73 | ~20 MB | ~50-250 MB | ~70-270 MB |
| **Windows Host** | ~40-50 | ~11-14 MB | ~50-150 MB | ~80-200 MB |
| **Windows + MSSQL** | ~55-65 | ~15-18 MB | ~50-150 MB | ~90-200 MB |

## 3. Cenário Prático de Exemplo

Projeção para um ambiente com **15 hosts** + **Stack LGTM** (Retenção 30d):

| Inventário | Unidades | Mimir (Métricas) | Loki (Logs) | Total Sugerido |
|---|---|---|---|---|
| **Stack LGTM** (Self-monitor) | 1 | 0.5 GB | 0.2 GB | 0.7 GB |
| **Hosts Linux** | 3 | 0.08 GB | 0.45 GB | 0.5 GB |
| **Hosts Linux + MySQL** | 2 | 0.04 GB | 0.30 GB | 0.34 GB |
| **Hosts Linux + PostgreSQL** | 2 | 0.07 GB | 0.30 GB | 0.37 GB |
| **Hosts Windows** | 4 | 0.06 GB | 0.40 GB | 0.46 GB |
| **Hosts Windows + SQL** | 3 | 0.05 GB | 0.30 GB | 0.35 GB |
| **TOTAL CONSOLIDADO** | **15 Hosts** | **~0.80 GB** | **~1.95 GB** | **~2.8 GB / mês** |

## 4. Fórmulas de Projeção

Se o seu ambiente crescer, use as seguintes equações para planejar o storage:

```
Métricas (GB) ≈ [Séries Ativas] × [Samples/hora] × 1.3 bytes × 24h × 30d × 2.5 overhead / 1024³
Simplificado:  ≈ [Séries Ativas] × 0.000270 GB/mês

Logs (GB) ≈ [Volume Bruto GB/dia] × 0.1 × [Dias de Retenção] × 1.5
```

**Referência rápida por tipo de host:**

| Tipo | Séries | GB/mês |
|---|---|---|
| Linux Host | ~98 | ~0.026 |
| Linux + PostgreSQL | ~128 | ~0.035 |
| Linux + MySQL | ~73 | ~0.020 |
| Windows | ~45 | ~0.012 |
| Windows + MSSQL | ~60 | ~0.016 |

## 5. Limites Físicos Sugeridos (Hardware Limiters)

Para o servidor central que executará a Stack LGTM:

- **Padrão Gold:** Em produção (alta carga de observabilidade), exija um host/VM com `8 Cores` e `32 GB RAM`.
- A distribuição de uso de núcleo padrão (via `compose.yaml`):
  - **Loki e Mimir:** ~2 vCPU / 6 GB a 8 GB RAM.
  - **Tempo:** ~2 vCPU / 6 GB RAM.
  - **Alloy Gateway e Grafana:** ~1 vCPU / 2 GB a 4 GB.
  - **Alloy Agent (Local):** ~0.5 vCPU / 1 GB.
- A soma do worst-case retém até 4 GB livres para o SO (bash, sshd).

---

# Detalhes Técnicos: Sizing Audit Report

## 1. Metodologia de Auditoria
A auditoria técnica foi realizada em três fases:
1. **Gap Analysis:** Cruzamento de todas as métricas recebidas pelo Mimir vs. métricas chamadas nas queries PromQL dos dashboards.
2. **Implementação de Whitelist:** Refatoração de todos os arquivos `.alloy` (Agente, Gateway e Templates) para utilizar filtros estritos de `keep`.
3. **Validação de Disco:** Limpeza total dos volumes de dados e medição do footprint real pós-otimização.

## 2. Especificação Técnica da Whitelist

### Linux (Node Exporter)
Foco em: Boot time, CPU, Load, Memory (Buffers, Cached, Available, Free, Total), PSI, Disk I/O (Read/Write/Written) e Network.
- **Séries auditadas:** ~98 (validado via Mimir, `job=linux-node`)
- **Arquivo:** `alloy-agent/conf.d/` ou `alloy-gateway/conf.d/pull-linux-*.alloy`

### Windows (Windows Exporter)
Foco em: Boot time, CPU Time, Physical Memory, Pagefile, Disk (Read/Write/Free) e Network.

### MSSQL Server
Foco em: Buffer Manager (Page Life Expectancy, Cache Hits), Database Stats (Log growths, Transactions), Locks (Deadlocks), Memory Manager e Wait Stats.

### PostgreSQL (postgres_exporter)
Foco em: Database size, Connections, Transactions (commit/rollback), Tuple ops (read/insert/update/delete), Temp files, Deadlocks, WAL size e Active time.
- **Séries auditadas:** ~68 métricas, total ~128 com node (validado via painéis)
- **Arquivo:** `alloy-gateway/conf.d/pull-linux-dbaas-pgsql-hosts.alloy`
- **Cardinalidade variável:** `pg_stat_activity_count` gera 24 séries (por estado de conexão), `pg_stat_database_*` gera 4 séries (por banco de dados)

### MySQL (mysqld_exporter)
Foco em: Status UP, Conexões, Threads, InnoDB Buffer Pool (data), InnoDB Row Operations (read/insert/update/delete), Locks (row lock waits), Tabelas temporárias, Redo Log size e Questions.
- **Séries auditadas:** ~13 métricas, total ~73 com node (validado via painéis)
- **Arquivo:** `alloy-gateway/conf.d/pull-linux-dbaas-mysql-hosts.alloy`

### Containers (cAdvisor)
Foco em: CPU usage, CPU periods/throttling, Memory working set, Memory usage (cache), OOM events e Network I/O.

## 3. Governança e Manutenção
- **Novos Dashboards:** Devem ser acompanhados da atualização das listas de `keep` nos arquivos `.alloy`.
- **Auto-Monitoramento:** Métricas `alloy_.*` disponíveis para debug, porém silenciadas por padrão para economia de disco.

---
**Documento validado por:** Antigravity (Coding Assistant)  
**Versão:** 1.3 (Lean Architecture — MySQL + PostgreSQL DBaaS)  
**Auditado em:** Abril/2026 — dados reais coletados do Mimir via API

---
🔙 Voltar: [README Principal](README.md)
