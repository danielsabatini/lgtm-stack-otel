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

A tabela abaixo compara o número de séries ativas geradas pelos coletores padrões de mercado contra a coleta filtrada da LGTM Stack:

| Tipo de Coletor / Alvo | Séries Brutas (Padrão) | Séries Filtradas (Nossa Stack) | Taxa de Economia Real |
|---|:---:|:---:|:---:|
| **Linux Host** (Node Exporter) | ~1.400 | **~98** | **-93.0%** 📉 |
| **Windows Host** (Windows Exporter) | ~450 | **~45** | **-90.0%** 📉 |
| **Windows + MSSQL Server** | ~800 | **~60** | **-92.5%** 📉 |
| **Containers Docker** (cAdvisor) | ~150 | **~8** | **-94.6%** 📉 |
| **Linux + DBaaS PostgreSQL** | ~1.300 | **~158** (86 host + 72 banco) | **-87.8%** 📉 |
| **Linux + DBaaS MySQL** | ~1.400 | **~99** (86 host + 13 banco) | **-92.9%** 📉 |
| **CoreDNS + etcd** (DNS Interno) | ~800 | **~120** | **-85.0%** 📉 |

---

## 4. Consumo Estimado de Armazenamento por Host / Mês

Valores baseados em auditoria real com retenção de **30 dias**, intervalo de coleta de **30 segundos** e overhead de compactação TSDB:

| Tipo de Host Monitorado | Séries Ativas | Mimir (Métricas/mês) | Loki (Logs/mês) | Consumo Total / Mês |
|---|:---:|:---:|:---:|:---:|
| **Linux Host** (Padrão) | ~98 | ~26 MB | ~50 a 250 MB | **~100 a 300 MB** |
| **Linux + DBaaS PostgreSQL** | ~158 | ~43 MB | ~50 a 250 MB | **~100 a 300 MB** |
| **Linux + DBaaS MySQL** | ~99 | ~27 MB | ~50 a 250 MB | **~80 a 280 MB** |
| **Windows Host** | ~45 | ~12 MB | ~50 a 150 MB | **~80 a 200 MB** |
| **Windows + MSSQL Server** | ~60 | ~16 MB | ~50 a 150 MB | **~90 a 200 MB** |

---

## 5. Cenário Prático de Exemplo (Ambiente com 15 Hosts)

Projeção de armazenamento para um ambiente corporativo com **15 servidores monitorados** e retenção de **30 dias**:

| Componente / Perfil de Host | Quantidade | Mimir (Métricas) | Loki (Logs) | Total Sugerido |
|---|:---:|:---:|:---:|:---:|
| **Stack LGTM Central** (Self-monitor) | 1 | ~0.50 GB | ~0.20 GB | ~0.70 GB |
| **Hosts Linux Padrão** | 3 | ~0.08 GB | ~0.45 GB | ~0.53 GB |
| **Hosts Linux + Banco MySQL** | 2 | ~0.05 GB | ~0.30 GB | ~0.35 GB |
| **Hosts Linux + Banco PostgreSQL** | 2 | ~0.09 GB | ~0.30 GB | ~0.39 GB |
| **Hosts Windows Padrão** | 4 | ~0.05 GB | ~0.40 GB | ~0.45 GB |
| **Hosts Windows + SQL Server** | 3 | ~0.05 GB | ~0.30 GB | ~0.35 GB |
| **TOTAL CONSOLIDADO** | **15 Servidores** | **~0.82 GB** | **~1.95 GB** | **~2.8 GB / mês** |

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
| **Produção Padrão (até 50 hosts)** | **8 vCPUs / 32 GB RAM** | • **Mimir:** 2 vCPU / 8 GB RAM<br/>• **Loki:** 2 vCPU / 6 GB RAM<br/>• **Tempo:** 2 vCPU / 6 GB RAM<br/>• **Grafana + Gateway:** 2 vCPU / 6 GB RAM<br/>• **SO (Livre):** ~4 GB RAM livre para sistema |

---

## 8. Governança e Referências

* Para a metodologia de pilares e conceitos de folga livre, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para detalhes sobre a política de métricas e allowlists, consulte [METRICS.md](METRICS.md).
* Para a política de retenção de logs, consulte [LOGS.md](LOGS.md).

---
🔙 Voltar: [README Principal](../README.md)
