# Dimensionamento e Estudo de Capacidade (Sizing)

> **Referência Técnica:** Este documento apresenta as fórmulas de projeção de disco, a memória necessária para a stack central e os resultados de auditoria de cardinalidade em modo Lean Observability.

---

## 1. Introdução

Bancos de dados de séries temporais (*TSDBs*) como o Mimir e agregadores de logs como o Loki podem sofrer de crescimento descontrolado de disco e memória se coletarem métricas sem filtragem. 

A LGTM Stack adota a estratégia **Lean Observability**: uma filtragem estrita na origem (*whitelisting*) que descarta na ponta tudo o que não é consumido pelos dashboards e alertas, reduzindo o volume de séries ativas em **mais de 90%**.

---

## 2. Objetivo

1. **Fornecer Estimativas Claras de Consumo:** Apresentar tabelas de projeção de disco e memória por host monitorado.
2. **Definir Requisitos de Hardware:** Especificar o dimensionamento ideal de CPU e memória RAM para a máquina que hospeda a stack.
3. **Disponibilizar Fórmulas de Planejamento:** Permitir que equipes de infraestrutura calculem com precisão a expansão de storage à medida que novos servidores forem adicionados.

---

## 3. Resumo dos Resultados de Cardinalidade (Lean Metrics)

Séries ativas **medidas** nos testes de validação de cada template (coleta a cada 30–60 s), comparadas ao que o coletor expõe sem filtro. A composição por fonte está em [METRICS.md](METRICS.md) §7.

| Tipo de servidor monitorado | Séries brutas (sem filtro) | Séries gravadas | Redução |
|---|:---:|:---:|:---:|
| **Linux** (agente: `system.*` + self-monitoring) | ~1.500 (`node_exporter`) | **~130** (67 host + ~63 agente) | **-91%** 📉 |
| **Windows** (agente) | ~1.650 (`windows_exporter`) | **~95** (30 host + ~65 agente) | **-94%** 📉 |
| **Linux + MySQL** (agente) | ~4.500 | **~170** (+38 banco) | **-96%** 📉 |
| **Linux + PostgreSQL** (agente, 2 bancos) | ~2.100 | **~160** (+~14 por banco) | **-92%** 📉 |
| **Windows + SQL Server** (agente, 1 instância) | ~1.850 | **~120** (+~25 por instância) | **-94%** 📉 |
| **Linux legado** (pull `node_exporter` → `system.*`) | ~1.550 | **~46** | **-97%** 📉 |
| **Windows legado** (pull `windows_exporter` → `system.*`) | ~1.650 | **~26** | **-98%** 📉 |
| **Windows + SQL Server legado** (pull, 2 instâncias) | ~1.650 | **~76** | **-95%** 📉 |
| **DBaaS MySQL** (pull, 4 vCPUs / 2 discos) | ~4.600 | **~91** (58 SO + 33 banco) | **-98%** 📉 |
| **DBaaS PostgreSQL** (pull, 2 bancos) | ~2.130 | **~88** (58 SO + 30 banco) | **-96%** 📉 |
| **Nó do cluster DNS** (pull node + CoreDNS + etcd) | ~2.100 | **~130** | **-94%** 📉 |
| **Container** do servidor da stack (`docker_stats`) | 13 | **7** | **-46%** 📉 |

> **Self-monitoring:** cada coletor envia suas próprias métricas (`otelcol_*`, `level: basic`): ~56 séries no `otel-gateway`, ~63 num agente de host e mais no `otel-agent` da stack (cresce com o número de coletas pull — ~123 com 6 templates). Num host simples isso é da mesma ordem das métricas de host; é o preço da visibilidade sobre a própria coleta.

---

## 4. Consumo Estimado de Armazenamento por Servidor / Mês

Retenção de **30 dias**, coleta a cada **30 segundos** e a fórmula da seção 6.1 (métricas). O volume de logs depende do servidor e do filtro de severidade na origem ([LOGS.md](LOGS.md)):

| Tipo de servidor | Séries ativas | Mimir (métricas/mês) | Loki (logs/mês) | Total / mês |
|---|:---:|:---:|:---:|:---:|
| **Linux** (agente) | ~130 | ~35 MB | ~50 a 250 MB | **~85 a 285 MB** |
| **Windows** (agente) | ~95 | ~26 MB | ~50 a 150 MB | **~75 a 175 MB** |
| **Linux + MySQL** (agente) | ~170 | ~46 MB | ~50 a 250 MB | **~95 a 295 MB** |
| **Linux + PostgreSQL** (agente) | ~160 | ~43 MB | ~50 a 250 MB | **~95 a 295 MB** |
| **Windows + SQL Server** (agente) | ~120 | ~32 MB | ~50 a 150 MB | **~80 a 180 MB** |
| **Linux legado** (pull) | ~46 | ~12 MB | — | **~12 MB** |
| **DBaaS MySQL / PostgreSQL** (pull) | ~91 / ~88 | ~25 / ~24 MB | — | **~25 MB** |

Servidores coletados por pull não enviam logs (só métricas do exporter).

---

## 5. Cenário Prático de Exemplo (Ambiente com 15 Servidores)

Projeção para **15 servidores** com retenção de **30 dias**:

| Componente / perfil | Quantidade | Mimir (métricas) | Loki (logs) | Total sugerido |
|---|:---:|:---:|:---:|:---:|
| **Servidor da stack** (otel-agent + gateway + containers) | 1 | ~0,10 GB | ~0,20 GB | ~0,30 GB |
| **Linux** (agente) | 3 | ~0,11 GB | ~0,45 GB | ~0,56 GB |
| **Linux + MySQL** (agente) | 2 | ~0,09 GB | ~0,30 GB | ~0,39 GB |
| **Linux + PostgreSQL** (agente) | 2 | ~0,09 GB | ~0,30 GB | ~0,39 GB |
| **Windows** (agente) | 4 | ~0,10 GB | ~0,40 GB | ~0,50 GB |
| **Windows + SQL Server** (agente) | 3 | ~0,10 GB | ~0,30 GB | ~0,40 GB |
| **TOTAL CONSOLIDADO** | **15 servidores** | **~0,59 GB** | **~1,95 GB** | **~2,5 GB / mês** |

---

## 6. Fórmulas de Projeção de Armazenamento

Para planejar a expansão do seu disco à medida que novos servidores forem adicionados, utilize as seguintes equações simplificadas:

### 6.1 Projeção de Métricas (Mimir TSDB)
$$\text{Storage Métricas (GB)} \approx \text{Total de Séries Ativas} \times 0.000270 \text{ GB/mês}$$

### 6.2 Projeção de Logs (Loki Chunks)
$$\text{Storage Logs (GB)} \approx \text{Volume Bruto Diário (GB/dia)} \times 0.1 \times \text{Dias de Retenção} \times 1.5$$

---

## 7. Requisitos de Hardware do Servidor Central (CPU e RAM)

Para a máquina virtual ou servidor físico que executará a Stack LGTM central:

| Perfil de Ambiente | Capacidade Recomendada | Distribuição de Recursos nos Containers |
|---|---|---|
| **Desenvolvimento / Laboratório** | **4 vCPUs / 8 GB RAM** | Recursos compartilhados sem limites estritos. |
| **Produção Padrão (até 50 hosts)** | **8 vCPUs / 32 GB RAM** | Tetos por container (`.env.example`):<br/>• **Mimir:** 2 vCPU / 8 GB<br/>• **Loki:** 2 vCPU / 6 GB<br/>• **Tempo:** 2 vCPU / 6 GB<br/>• **Grafana:** 1 vCPU / 4 GB<br/>• **OTel Gateway:** 1 vCPU / 2 GB<br/>• **otel-agent:** 0,5 vCPU / 512 MB<br/>• **Soma dos tetos:** 8,5 vCPU / 26,5 GB (~5,5 GB livres para o SO) |

---

## 8. Governança e Referências

* Para a metodologia de pilares e conceitos de folga livre, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para detalhes sobre a política de métricas e allowlists, consulte [METRICS.md](METRICS.md).
* Para a política de retenção de logs, consulte [LOGS.md](LOGS.md).

---
🔙 Voltar: [README Principal](../README.md)
