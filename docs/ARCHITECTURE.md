# Arquitetura Física e Lógica (LGTM Stack)

> **Referência Técnica:** Este documento descreve a topologia de rede, o isolamento de segurança e as responsabilidades arquiteturais de cada componente da LGTM Stack.

---

## 1. Introdução

Em arquiteturas convencionais de observabilidade, o coletor de telemetria é frequentemente configurado como um único processo com privilégios de administrador (`root`) para inspecionar o sistema operacional e, ao mesmo tempo, exposto diretamente à rede externa para receber dados de aplicações. Esse modelo cria uma vulnerabilidade crítica de segurança.

A LGTM Stack elimina esse risco através do desacoplamento em dois papéis fundamentais: o **Alloy Agent** (coleta local segura) e o **Alloy Gateway** (ingestão e roteamento desprivilegiado).

---

## 2. Objetivo

1. **Garantir Isolamento de Segurança:** Impedir que processos com privilégios elevados fiquem expostos a conexões de rede externa.
2. **Definir Fronteiras de Rede:** Centralizar toda a ingestão da stack em um único componente sem privilégios (Gateway).
3. **Proteger os Bancos de Dados (TSDBs):** Manter Loki, Mimir e Tempo totalmente isolados da rede pública, permitindo leitura exclusivamente através do Grafana.

---

## 3. Topologia Geral (Padrão Gateway-Agent)

A divisão de responsabilidades entre coleta no host e recepção na rede é estruturada através do desacoplamento de privilégios e isolamento de segurança:

![Topologia Geral da LGTM Stack](diagrams/lgtm-architecture-topology.png)

<details>
<summary>📐 Exibir código-fonte Mermaid do diagrama</summary>

```mermaid
flowchart TB
    %% Estilos e Classes
    classDef hostBox fill:#f8f9fa,stroke:#495057,stroke-width:2px,color:#212529;
    classDef privBox fill:#fff3bf,stroke:#f59f00,stroke-width:2px,color:#d9480f;
    classDef gtwBox fill:#d0ebff,stroke:#1971c2,stroke-width:2px,color:#1864ab;
    classDef tsdbBox fill:#e6fcf5,stroke:#0ca678,stroke-width:2px,color:#087f5b;
    classDef uiBox fill:#f3d9fa,stroke:#ae3ec9,stroke-width:2px,color:#862e9c;
    classDef extBox fill:#f1f3f5,stroke:#868e96,stroke-dasharray: 4 4,color:#495057;

    subgraph EXT ["🌐 Aplicações & Servidores Remotos (Rede / VPC)"]
        APP1["🖥️ Hosts Remotos<br/>(Alloy Agent / Node Exporter)"]:::extBox
        APP2["📦 Aplicações Microservices<br/>(OTLP Traces / Metrics)"]:::extBox
        APP3["📜 Emissores de Logs<br/>(Loki Push / Fluentd)"]:::extBox
    end

    subgraph STACK ["🏛️ Servidor Central (LGTM Stack)"]
        subgraph PRIV ["🛡️ Camada Host / Kernel (Modo Privilegiado)"]
            AGENT["⚡ Alloy Agent (Host Local)<br/>• privileged: true<br/>• Lê /proc, /sys, /rootfs<br/>• Coleta Journald e Docker Socket"]:::privBox
        end

        subgraph UNPRIV ["🕸️ Camada de Ingestão de Rede (Modo Seguro / Desprivilegiado)"]
            GATEWAY["🚪 Alloy Gateway<br/>• privileged: false (Unprivileged)<br/>• Portas: 4317 (gRPC), 4318 (HTTP), 9998 (Loki), 9999 (Mimir)<br/>• Autenticação, Relabel e Fan-out de Telemetria"]:::gtwBox
        end

        subgraph BACKENDS ["🗄️ Bancos de Dados TSDB (Rede Interna Docker 'lgtm' - Sem Exposição Pública)"]
            LOKI[("📜 Grafana Loki<br/>Armazenamento de Logs")]:::tsdbBox
            MIMIR[("📈 Grafana Mimir<br/>Armazenamento de Métricas")]:::tsdbBox
            TEMPO[("🔍 Grafana Tempo<br/>Armazenamento de Traces")]:::tsdbBox
        end

        subgraph FRONTEND ["📊 Camada de Visualização & Acesso"]
            GRAFANA["🖥️ Grafana UI<br/>• Porta 3000 (Leitura / Painéis)<br/>• Consultas unificadas PromQL, LogQL, TraceQL"]:::uiBox
        end
    end

    %% Conexões e Fluxos
    AGENT -->|"Push HTTP Interno<br/>(Sem porta exposta)"| GATEWAY
    APP1 -->|"Prometheus Remote Write<br/>(Porta 9999)"| GATEWAY
    APP2 -->|"OTLP gRPC / HTTP<br/>(Portas 4317 / 4318)"| GATEWAY
    APP3 -->|"Loki Push API<br/>(Porta 9998)"| GATEWAY

    GATEWAY -->|"Gravação de Logs"| LOKI
    GATEWAY -->|"Gravação de Métricas"| MIMIR
    GATEWAY -->|"Gravação de Traces"| TEMPO

    GRAFANA -.->|"Datasource Proxy (LogQL)"| LOKI
    GRAFANA -.->|"Datasource Proxy (PromQL)"| MIMIR
    GRAFANA -.->|"Datasource Proxy (TraceQL)"| TEMPO

    USER["👨‍💻 Engenheiros & Operadores"]:::extBox -->|"HTTPS / Porta 3000<br/>(Visualização de Dashboards)"| GRAFANA
```
</details>

---

## 4. Componentes e Papéis da Stack

### 4.1 Alloy Gateway (Ingestão e Roteamento)
Roda sem privilégios elevados e atua como o **ponto único de entrada** para toda a telemetria que chega pela rede:
* **Portas 4317 (gRPC) e 4318 (HTTP):** Ingestão de traces e métricas no padrão OpenTelemetry (OTLP).
* **Porta 9999:** Recebimento de métricas no padrão Prometheus `remote_write`.
* **Porta 9998:** Recebimento de logs via API de push do Grafana Loki.
* **Roteamento:** Encaminha métricas para o Mimir, logs para o Loki e traces para o Tempo.

> ⚠️ **Regra Arquitetural Inviolável:** Todo envio de métricas (`prometheus.remote_write`) — seja do agente local, de agentes remotos ou de coletas pull — deve apontar para `http://alloy-gateway:9999/api/v1/metrics/write`. **Nunca escreva diretamente no Mimir (`mimir:9009`)**.

### 4.2 Alloy Agent (Coleta Local no Host)
Roda com permissões administrativas (`privileged: true`) para inspecionar o estado do sistema operacional e contêineres:
* Lê `/proc`, `/sys` e `/rootfs` para extrair métricas de CPU, memória, disco e rede.
* Lê os arquivos de log do systemd journal e do socket Docker.
* Não expõe nenhuma porta de recebimento na rede pública — envia tudo via push interno para o Gateway.

### 4.3 Backends Distroless (Loki, Mimir e Tempo)
As bases de dados utilizam imagens *distroless* (sem shell e sem utilitários de sistema operacional desnecessários):
* Não possuem portas publicadas no host — são acessíveis exclusivamente dentro da rede interna Docker `lgtm`.
* Não utilizam healthcheck baseado em `CMD-SHELL`.
* Para procedimentos de upgrade e verificação de saúde, consulte [UPGRADE.md](UPGRADE.md).

### 4.4 Grafana (Camada de Visualização)
* É o único ponto de consulta e leitura de dados para os usuários e operadores.
* Conecta-se internamente aos backends (Mimir, Loki, Tempo) através dos datasources provisionados como código.

---

## 5. Requisitos de Firewall e Portas de Rede

Para permitir que agentes remotos enviem dados e os operadores acessem os painéis, configure as seguintes regras no firewall do host (`ufw`/`iptables`) e no Security Group da nuvem (Magalu Cloud, AWS, etc.):

| Porta | Protocolo | Origem Recomendada | Descrição do Serviço |
|---|---|---|---|
| **`3000`** | TCP | Pública (Internet / VPN) | Acesso à interface web do **Grafana**. |
| **`12345`** | TCP | VPN / Admin | Acesso à interface web de diagnóstico do **Alloy Gateway**. |
| **`4317`** | TCP | Rede Interna (VPC / VPN) | Ingestão OTLP gRPC (Traces e Métricas de Aplicações). |
| **`4318`** | TCP | Rede Interna (VPC / VPN) | Ingestão OTLP HTTP (Traces e Métricas de Aplicações). |
| **`9998`** | TCP | Rede Interna (VPC / VPN) | Ingestão de Logs via Loki Push API. |
| **`9999`** | TCP | Rede Interna (VPC / VPN) | Ingestão de Métricas via Prometheus Remote Write. |

> 🔒 **Recomendação de Segurança:** Nunca abra as portas de ingestão (`4317`, `4318`, `9998`, `9999`) diretamente para a internet aberta. O tráfego de telemetria entre servidores remotos e a stack central deve trafegar através de VPN, VPC Peering ou túneis criptografados.

---

## 6. Governança e Referências

* Para dimensionamento de hardware e disco, consulte [SIZING.md](SIZING.md).
* Para a metodologia e taxonomia de organização de painéis, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para procedimentos de backup e recuperação, consulte [BACKUP.md](BACKUP.md).

---
🔙 Voltar: [README Principal](../README.md)
