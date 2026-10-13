# Arquitetura Física e Lógica (LGTM Stack)

> **Referência Técnica:** Este documento descreve a topologia de rede, o isolamento de segurança e as responsabilidades arquiteturais de cada componente da LGTM Stack.

---

## 1. Introdução

Em arquiteturas convencionais de observabilidade, o coletor de telemetria é frequentemente configurado como um único processo com privilégios de administrador (`root`) para inspecionar o sistema operacional e, ao mesmo tempo, exposto diretamente à rede externa para receber dados de aplicações. Esse modelo cria uma vulnerabilidade crítica de segurança.

A LGTM Stack elimina esse risco através do desacoplamento em dois papéis fundamentais: o **Agent** (OpenTelemetry Collector + OBI no host, coleta local segura) e o **OTel Gateway** (OpenTelemetry Collector) (ingestão e roteamento desprivilegiado).

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
        APP1["🖥️ Hosts com Agente (push)<br/>(OTel Collector + OBI)"]:::extBox
        APP2["📦 Aplicações Microservices<br/>(OTLP Traces / Metrics)"]:::extBox
        APP3["📜 Emissores de Logs<br/>(OTLP Logs)"]:::extBox
        LEGACY["🗃️ Servidores Legados sem Agente (pull)<br/>(node_exporter :9100, windows_exporter :9182,<br/>exporters de DBaaS, CoreDNS / etcd)"]:::extBox
    end

    subgraph STACK ["🏛️ Servidor Central (LGTM Stack)"]
        subgraph PRIV ["🛡️ Camada Host (Leitura do Host, Sem Portas Expostas)"]
            AGENT["⚡ otel-agent (servidor da stack)<br/>• root sem capabilities, mounts read-only<br/>• host_metrics, docker_stats, journald<br/>• Pull de exporters legados (pull.d)"]:::privBox
        end

        subgraph UNPRIV ["🕸️ Camada de Ingestão de Rede (Modo Seguro / Desprivilegiado)"]
            GATEWAY["🚪 OTel Gateway (otelcol-contrib)<br/>• privileged: false (Unprivileged)<br/>• Portas: 4317 (OTLP gRPC), 4318 (OTLP HTTP)<br/>• Somente OTLP: sampling, batch e fan-out sem conversão"]:::gtwBox
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
    AGENT -->|"OTLP local<br/>(127.0.0.1:4317)"| GATEWAY
    LEGACY -.->|"Métricas via scrape HTTP<br/>(conexão iniciada pelo otel-agent)"| AGENT
    APP1 -->|"OTLP Métricas, Logs e Traces<br/>(Portas 4317 / 4318)"| GATEWAY
    APP2 -->|"OTLP gRPC / HTTP<br/>(Portas 4317 / 4318)"| GATEWAY
    APP3 -->|"OTLP Logs<br/>(Portas 4317 / 4318)"| GATEWAY

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

### 4.1 OTel Gateway (Ingestão e Roteamento)
Roda sem privilégios elevados e atua como o **ponto único de entrada** para toda a telemetria que chega pela rede:
* **Portas 4317 (gRPC) e 4318 (HTTP):** Única entrada da stack — traces, métricas e logs no padrão OpenTelemetry (OTLP), vindos dos agents e das aplicações.
* **Health check:** porta 13133 (`curl http://localhost:13133/`). As métricas internas do Gateway (nível `basic`) são gravadas no Mimir com `service.name="otel-gateway"`.
* **Roteamento:** Encaminha cada sinal ao seu backend em **OTLP nativo**: métricas → Mimir (`/otlp/v1/metrics`), logs → Loki (`/otlp/v1/logs`), traces → Tempo (gRPC). O Gateway não converte nem renomeia dados: só aplica `memory_limiter`, tail sampling de traces e `batch` (`otel-gateway/config.yaml`).

> ⚠️ **Regras Arquiteturais Invioláveis:**
> 1. **Só o OTel Gateway escreve nos backends.** Agentes, aplicações e os próprios backends nunca escrevem direto em `mimir:9009`, `loki:3100` ou `tempo:4317`.
> 2. **Cada backend armazena apenas o seu sinal** (métricas → Mimir, logs → Loki, traces → Tempo). Por isso o `metrics_generator` do Tempo fica desabilitado.
> 3. **O dado sai da origem já correto**: OTLP com a [OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/). Conversões acontecem no agente, nunca no Gateway.

Verificação de que só há escrita OTLP nos backends (contadores por rota, rede interna `lgtm`):

```bash
docker run --rm --network lgtm curlimages/curl -s http://mimir:9009/metrics \
  | grep -E 'cortex_request_duration_seconds_count\{.*route="(api_v1_push|otlp_v1_metrics)"'   # só otlp_v1_metrics
docker run --rm --network lgtm curlimages/curl -s http://loki:3100/metrics \
  | grep -E 'loki_request_duration_seconds_count\{.*route="(loki_api_v1_push|otlp_v1_logs)"'    # só otlp_v1_logs
```

### 4.2 Agent (Coleta Local no Host)
Instalado em cada host monitorado (templates em `examples/push/`), sem portas expostas na rede:
* **OpenTelemetry Collector Contrib** (`otelcol-contrib`, pacote oficial, serviço systemd): métricas de host (`host_metrics`, nomes `system.*`), logs do journald, identidade OpenTelemetry do host (`OTEL_RESOURCE_ATTRIBUTES` + detector `system`) e a única saída OTLP para o Gateway, com fila e reenvio quando o Gateway está indisponível.
* **OBI** (OpenTelemetry eBPF Instrumentation, serviço `obi`, opcional): traces e métricas HTTP/gRPC/SQL via eBPF, sem alterar o código, com propagação de contexto W3C. Envia OTLP ao Collector local (`127.0.0.1:4317`) e roda com usuário dedicado e capabilities eBPF, não como root.

> **Servidor da própria stack:** o serviço `otel-agent` do `compose.yaml` é o mesmo Collector em container (`otel-agent/Dockerfile`: binário oficial + `journalctl`), com `network_mode: host` e `pid: host` para enxergar a rede e os processos do host, root **sem nenhuma capability** (`cap_drop: ALL`, `no-new-privileges`) e todos os mounts somente leitura (`/` em `/hostfs`, socket do Docker, logs de containers, journal). Além do host, coleta métricas (`docker_stats`) e logs **só dos containers da stack** — o filtro usa o projeto compose (`com.docker.compose.project`), então containers de outros projetos no mesmo servidor não são gravados. Não expõe portas (o self-monitoring usa `127.0.0.1:14317`). O `host.name` desse servidor é fixo, definido por `LGTM_HOST_NAME` no `.env` (padrão `lgtm-stack`), em vez do hostname da máquina.
>
> **Servidores legados sem agente (pull):** o `otel-agent` também carrega os arquivos `otel-agent/pull.d/*.yaml` (templates em `examples/pull/`) e faz o scrape dos exporters remotos (`node_exporter`, `windows_exporter`, exporters de DBaaS MySQL/PostgreSQL, CoreDNS/etcd), convertendo para OTLP com a identidade OpenTelemetry declarada por alvo e para o **mesmo formato do agente** (nomes, atributos e semântica da OTel Semantic Conventions — `otel-agent/pull-semconv.yaml`; ver [METRICS.md](METRICS.md) §7.1). Push e pull são indistinguíveis no Mimir e nos dashboards. Ele só **inicia** conexões (stack → porta do exporter, ex.: `:9100`/`:9182`), sem abrir portas; o exporter remoto deve aceitar conexões apenas do IP da stack. Servidores coletados por pull não enviam logs nem traces.

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
| **`13133`** | TCP | VPN / Admin | Health check do **OTel Gateway**. |
| **`4317`** | TCP | Rede Interna (VPC / VPN) | Ingestão OTLP gRPC (traces, métricas e logs de agents e aplicações). |
| **`4318`** | TCP | Rede Interna (VPC / VPN) | Ingestão OTLP HTTP (traces, métricas e logs de agents e aplicações). |

> 🔒 **Recomendação de Segurança:** Nunca abra as portas de ingestão (`4317`, `4318`) diretamente para a internet aberta. O tráfego de telemetria entre servidores remotos e a stack central deve trafegar através de VPN, VPC Peering ou túneis criptografados.

---

## 6. Governança e Referências

* Para dimensionamento de hardware e disco, consulte [SIZING.md](SIZING.md).
* Para a metodologia e taxonomia de organização de painéis, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para procedimentos de backup e recuperação, consulte [BACKUP.md](BACKUP.md).

---
🔙 Voltar: [README Principal](../README.md)
