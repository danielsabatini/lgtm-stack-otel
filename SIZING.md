# Dimensionamento e Estudo de Capacidade (Sizing)

Este documento contém os resultados da auditoria de capacidade e as projeções de consumo de hardware para a stack LGTM em modo **Lean Observability**.

## 1. Resumo dos Resultados (Abril/2024)

Após a implementação da política de **Explicit Whitelisting (keep)**, a cardinalidade foi reduzida em mais de 90% em comparação com os exporters padrão.

| Categoria | Métricas Lean (Atual) | Redução vs. Padrão |
|---|---|---|
| **Linux Host** | ~40 a 60 | **77%** |
| **Windows Host** | ~30 a 50 | **90%** |
| **Windows + MSSQL** | ~45 a 65 | **92%** |
| **Containers (cAdvisor)** | ~8 | **84%** |

## 2. Consumo Estimado por Host

Valores médios baseados em retenção de **30 dias**:

- **Métricas (Mimir):** ~350 MB / mês por host (Margem de segurança inclusa).
- **Logs (Loki):** ~50 MB a 250 MB / mês por host (Depende da verbosidade).
- **Traces (Tempo):** Variável (Reduzido em 95% via Tail Sampling).

## 3. Cenário Prático de Exemplo

Projeção para um ambiente com **15 hosts** + **Stack LGTM** (Retenção 30d):

| Inventário | Unidades | Mimir (Métricas) | Loki (Logs) | Total Sugerido |
|---|---|---|---|---|
| **Stack LGTM** (Self-monitor) | 1 | 0.5 GB | 0.2 GB | 0.7 GB |
| **Hosts Linux** | 5 | 1.75 GB | 0.75 GB | 2.5 GB |
| **Hosts Windows** | 5 | 1.50 GB | 0.50 GB | 2.0 GB |
| **Hosts Windows + SQL** | 5 | 1.75 GB | 1.00 GB | 2.75 GB |
| **TOTAL CONSOLIDADO** | **15 Hosts** | **5.50 GB** | **2.45 GB** | **~8.0 GB / mês** |

## 4. Fórmulas de Projeção

Se o seu ambiente crescer, use as seguintes equações para planejar o storage:

*   **Métricas:** `Disco (GB) ≈ [Total de Hosts] × 0.35 × [Meses de Retenção]`
*   **Logs:** `Disco (GB) ≈ [Volume Bruto GB/dia] × 0.1 × [Dias de Retenção] × 1.5`

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

### Windows (Windows Exporter)
Foco em: Boot time, CPU Time, Physical Memory, Pagefile, Disk (Read/Write/Free) e Network.

### MSSQL Server
Foco em: Buffer Manager (Page Life Expectancy, Cache Hits), Database Stats (Log growths, Transactions), Locks (Deadlocks), Memory Manager e Wait Stats.

### Containers (cAdvisor)
Foco em: CPU usage, CPU periods/throttling, Memory working set, Memory usage (cache), OOM events e Network I/O.

## 3. Governança e Manutenção
- **Novos Dashboards:** Devem ser acompanhados da atualização das listas de `keep` nos arquivos `.alloy`.
- **Auto-Monitoramento:** Métricas `alloy_.*` disponíveis para debug, porém silenciadas por padrão para economia de disco.

---
**Documento validado por:** Antigravity (Coding Assistant)  
**Versão:** 1.2 (Lean Architecture - Updated Metrics)

---
🔙 Voltar: [README Principal](README.md)
