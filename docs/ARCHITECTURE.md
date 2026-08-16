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

A divisão de responsabilidades entre coleta no host e recepção na rede é estruturada da seguinte forma:

```text
 🛡️ HOST / KERNEL (Modo Privilegiado)              🕸️ REDE / APLICAÇÕES (Modo Seguro)
 ─────────────────────────────────────              ───────────────────────────────────

  [Alloy Agent] ──────(Push HTTP Interno)────────▶  [Alloy Gateway] ◀──(OTLP Logs/Metrics/Traces)
  - Roda como Root / Privileged                     - Roda sem privilégios (Unprivileged)
  - Lê CPU, Memória, Disco (/procfs, /sys)          - Escuta portas 4317, 4318, 9998, 9999
  - Lê Journald e Docker Socket                     - Faz fanout e roteamento para os backends
        │                                                   │
        ▽ (Isolado da Rede Externa)                         ▽
       N/A                                      ┌───────────o───────────┐
                                                │                       │
                                             [Loki]  [Mimir]  [Tempo]   │
                                                │       │        │      │
                                                └───────o────────┘      │
                                                        ▽               │
                                                    [Grafana] ◀─────────┘
                                                 (Porta 3000 - Leitura)
```

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
