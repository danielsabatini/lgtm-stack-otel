# LGTM Stack — Observabilidade Desacoplada e Lean

> **Referência Central:** Arquitetura de referência completa para observabilidade corporativa utilizando **Grafana, Grafana Alloy, Grafana Loki, Grafana Mimir e Grafana Tempo (LGTMP)**, focada em segurança por isolamento de privilégios e eficiência de custos (*Lean Observability*).

---

## 1. Introdução

Em ambientes tradicionais de monitoramento, a infraestrutura de telemetria frequentemente sofre com dois problemas graves: vulnerabilidades de segurança (coletores com privilégios de `root` expostos diretamente à rede externa) e custos proibitivos de armazenamento causados pela coleta indiscriminada de métricas que nunca são consultadas.

A **LGTM Stack** resolve esses desafios através do desacoplamento arquitetural entre **Alloy Agent** (coleta local privilegiada sem portas de rede) e **Alloy Gateway** (ingestão segura desprivilegiada), combinada com uma política estrita de *Explicit Allowlisting (Lean Metrics)* que reduz a cardinalidade e o consumo de disco em mais de **80% a 90%** em relação ao padrão de mercado.

---

## 2. Objetivo

1. **Unificar os 3 Sinais da Observabilidade:** Centralizar Métricas (Mimir), Logs (Loki) e Traces Distribuídos (Tempo) em uma interface única no Grafana 13.
2. **Garantir Segurança por Design:** Isolar totalmente os bancos de dados TSDBs da rede pública, expondo apenas o Alloy Gateway para recepção desprivilegiada e o Grafana para leitura autenticada.
3. **Fornecer Soluções Prontas para Produção:** Entregar dashboards provisionados como código (*GitOps*), documentação metodológica padronizada e templates de agentes para Linux, Windows, bancos de dados (MySQL, PostgreSQL, MSSQL) e infraestrutura de DNS interno (*CoreDNS + etcd*).

---

## 3. Estrutura e Entregáveis do Repositório

O repositório é organizado de forma modular e determinística:

* **`compose.yaml`:** Declaração principal dos serviços da stack central (Loki, Mimir, Tempo, Grafana, Alloy Gateway e Alloy Agent local).
* **`alloy-agent/conf.d/`:** Pipelines HCL para coleta local de métricas de host (CPU, Memória, Disco, Rede, Inodes), containers Docker e logs do systemd journal.
* **`alloy-gateway/conf.d/`:** Ponto único de ingestão de rede com suporte a OTLP (4317/4318), Prometheus `remote_write` (9999) e Loki Push (9998).
* **`grafana/provisioning/`:** Fonte única da verdade para Datasources (Mimir, Loki, Tempo) e Dashboards nativos do Grafana 13 (`dashboard.grafana.app/v2`).
* **`examples/push/`:** Templates de instalação para agentes locais Alloy nos servidores monitorados (Linux, Windows, Linux MySQL, Linux PostgreSQL, Windows MSSQL).
* **`examples/pull/`:** Templates de scraping remoto (modo Pull) para serem carregados no Alloy Gateway central (Linux Host, Linux DNS, CoreDNS, etcd, DBaaS MySQL, DBaaS PostgreSQL, Windows).
* **`artifacts/`:** Scripts de teste de carga (DNS, MySQL, PostgreSQL), automação de túneis e planilhas de referência.
* **`docs/`:** Documentação oficial, técnica e operacional da stack.

---

## 4. Início Rápido (Ambiente Local / Laboratório)

> ⚠️ **Pré-requisito:** Certifique-se de ter o **Docker** e o **Docker Compose (V2)** instalados. Para requisitos de hardware e particionamento de disco dedicado (`/docker`), consulte [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md).

Para subir a stack central em ambiente local ou de desenvolvimento:

```bash
# 1. Clonar o repositório
git clone https://github.com/danielsabatini/lgtm-stack.git
cd lgtm-stack

# 2. Configurar as variáveis de ambiente
cp .env.example .env

# 3. Inicializar a stack completa
docker compose up -d
```

Após a inicialização:
* **Grafana UI:** Acesse `http://localhost:3000` (Usuário: `admin` / Senha definida no `.env`, padrão: `changeme`).
* **Alloy Gateway UI:** Acesse `http://localhost:12345` para diagnóstico de componentes e pipelines.

---

## 5. Coleta em Servidores Remotos (Agentes Push & Scrapes Pull)

Para monitorar instâncias remotas, consulte o guia de instalação correspondente ao modo de coleta:

| Plataforma / Carga de Trabalho | Modo de Coleta | Guia Passo a Passo |
|---|---|---|
| **Linux (Debian / Ubuntu / Rocky)** | Push (Agente Local) | [examples/push/linux/INSTALL.md](examples/push/linux/INSTALL.md) |
| **Linux + MySQL Nativo** | Push (Agente Local) | [examples/push/linux-mysql/INSTALL.md](examples/push/linux-mysql/INSTALL.md) |
| **Linux + PostgreSQL Nativo** | Push (Agente Local) | [examples/push/linux-pgsql/INSTALL.md](examples/push/linux-pgsql/INSTALL.md) |
| **Windows Server** | Push (Agente Local) | [examples/push/windows/INSTALL.md](examples/push/windows/INSTALL.md) |
| **Windows + SQL Server (MSSQL)** | Push (Agente Local) | [examples/push/windows-mssql/INSTALL.md](examples/push/windows-mssql/INSTALL.md) |
| **Linux Host Geral (Node Exporter)** | Pull Remoto (Gateway) | [examples/pull/linux/INSTALL.md](examples/pull/linux/INSTALL.md) |
| **Windows Server (Windows Exporter)** | Pull Remoto (Gateway) | [examples/pull/windows/INSTALL.md](examples/pull/windows/INSTALL.md) |
| **Windows + SQL Server (MSSQL)** | Pull Remoto (Gateway) | [examples/pull/windows-mssql/INSTALL.md](examples/pull/windows-mssql/INSTALL.md) |
| **Linux + DBaaS MySQL** | Pull Remoto (Gateway) | [examples/pull/linux-dbaas-mysql/INSTALL.md](examples/pull/linux-dbaas-mysql/INSTALL.md) |
| **Linux + DBaaS PostgreSQL** | Pull Remoto (Gateway) | [examples/pull/linux-dbaas-pgsql/INSTALL.md](examples/pull/linux-dbaas-pgsql/INSTALL.md) |
| **Cluster DNS Interno (CoreDNS + etcd)** | Pull Remoto (Gateway) | [examples/pull/dns/INSTALL.md](examples/pull/dns/INSTALL.md) |

> 🔍 **Auto-Instrumentação de Traces (Beyla eBPF):** Disponível como módulo sem código no guia Linux ([examples/push/linux/INSTALL.md](examples/push/linux/INSTALL.md#51-traces-beyla-ebpf--opcional)). Para arquitetura de traces, consulte [docs/TRACES.md](docs/TRACES.md).

---

## 6. Endpoints e Fronteiras de Rede

A stack opera com isolamento estrito de portas. Nenhum banco de dados (TSDB) é exposto na rede pública:

| Porta | Protocolo | Origem Recomendada | Descrição do Serviço |
|---|---|---|---|
| **`3000`** | TCP | Pública / VPN | Interface Web e leitura de Dashboards no **Grafana**. |
| **`12345`** | TCP | VPN / Admin | Interface Web de diagnóstico do **Alloy Gateway**. |
| **`4317`** | TCP | VPC / Rede Interna | Ingestão OTLP gRPC (Traces e Métricas de Aplicações). |
| **`4318`** | TCP | VPC / Rede Interna | Ingestão OTLP HTTP (Traces e Métricas de Aplicações). |
| **`9998`** | TCP | VPC / Rede Interna | Ingestão de Logs via Loki Push API. |
| **`9999`** | TCP | VPC / Rede Interna | Ingestão de Métricas via Prometheus Remote Write. |

> 📖 Para diagrama visual de rede e topologia de segurança, consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 7. Catálogo da Documentação Oficial (Governança)

> 🔒 **Regra de Fonte Única da Verdade (`AGENTS.md` §11.1.6):** Cada documento abaixo é a referência normativa exclusiva sobre o seu respectivo tema. Informações técnicas não são duplicadas entre arquivos.

### 7.1 Arquitetura, Infraestrutura e Operação
* **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):** Topologia de rede, modelo Gateway-Agent e isolamento de segurança.
* **[docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md):** Pré-requisitos, particionamento de disco LVM (`/docker`) e volumes.
* **[docs/SIZING.md](docs/SIZING.md):** Dimensionamento de hardware, cardinalidade real e projeção de retenção de disco.
* **[docs/BACKUP.md](docs/BACKUP.md):** Procedimentos de backup, snapshot de volumes e Disaster Recovery (DR).
* **[docs/UPGRADE.md](docs/UPGRADE.md):** Roteiro seguro de upgrade de componentes e compatibilidade de TSDBs.

### 7.2 Sinais de Telemetria e Visualização
* **[docs/OBSERVABILITY-METHODOLOGY.md](docs/OBSERVABILITY-METHODOLOGY.md):** Metodologia canônica dos 5 Pilares Numéricos (*Health, Capacity, Activity, Diagnostics, Inventory*), 4 Categorias de Logs, Traces OTLP, SLIs/SLOs e Playbook de Incidentes.
* **[docs/METRICS.md](docs/METRICS.md):** Política de métricas Lean, allowlists e padrão de tooltips em 3 blocos.
* **[docs/LOGS.md](docs/LOGS.md):** Política de logs estruturados no Loki, estágios de relabel e parsing.
* **[docs/TRACES.md](docs/TRACES.md):** Rastreamento distribuído no Tempo, Beyla eBPF e tail-sampling.
* **[docs/DASHBOARDS.md](docs/DASHBOARDS.md):** Provisionamento GitOps com schema nativo do Grafana 13 (`v2`), convenções visuais e arquitetura da solução DNS.
* **[docs/ALERTS.md](docs/ALERTS.md):** Estratégia de regras de alerta por taxa de queima de SLO (*Multi-Window Multi-Burn-Rate*).

### 7.3 Governança do Repositório
* **[README.md](README.md):** Porta de entrada, visão geral e orientações iniciais.
* **[CHANGELOG.md](CHANGELOG.md):** Histórico de releases e mudanças estruturadas por versão.
* **[CONTRIBUTING.md](CONTRIBUTING.md):** Padrões de código, diretrizes de contribuição e convenções técnicas.
* **[ROADMAP.md](ROADMAP.md):** Planejamento evolutivo e marcos futuros do projeto.
* **[LICENSE](LICENSE):** Licença e termos de distribuição do projeto (MIT License).

---

## 8. Termo de Responsabilidade e Limites de Suporte

* **Natureza da Solução:** Esta solução (*LGTM Stack*) é uma arquitetura de referência baseada em projetos *Open Source* de terceiros (Grafana Labs) executada no espaço do usuário via Docker. Ela **não é** um serviço gerenciado (PaaS) proprietário.
* **Fronteira de Suporte em Cloud:** Em ambientes de nuvem (como Magalu Cloud), o suporte oficial do provedor limita-se exclusivamente à infraestrutura subjacente (disponibilidade das máquinas virtuais, conectividade de rede da VPC e integridade dos volumes de bloco). A depuração de processos internos dos containers, consultas PromQL/LogQL customizadas, ajustes de sizing e políticas de backup são de responsabilidade do administrador da stack.
* **Responsabilidade Operacional:** O mantenedor da stack assume a gestão da capacidade de hardware, rotação de logs e aplicação periódica de atualizações de segurança recomendadas em [docs/UPGRADE.md](docs/UPGRADE.md).
