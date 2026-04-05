# Arquitetura Física e Lógica (LGTM Stack)

Este documento detalha o esqueleto e funcionamento da nossa _stack_ de Observabilidade, pautada em conceitos de "Segurança por Isolamento" (Zero-Trust) e "Redução de Cardinalidade na Borda".

## Topologia Geral (O Efeito Gateway-Agent)

Em arquiteturas convencionais, o coletor de telemetria é um processo inflado com poderes de `root` para varrer discos, e simultaneamente exposto à rede web para receber chamadas de APIs. **Nós abolimos essa vulnerabilidade.**

Decidimos separar os pilares do Grafana Alloy:

```text
 🛡️ HOST / KERNEL                                     🕸️ REDE CORPORATIVA / APPs
 ─────────────────                                  ───────────────────────────

  [Alloy Agent] ──────(Push HTTP Interno)────────▶  [Alloy Gateway] ◀──(OTLP Logs/Metrics/Traces)
  - Modo Root                                       - Modo Unpriviliged
  - Lê CPU/Memória                                  - Escuta Portas 4317 / 4318
  - Lê Journald                                     - Repassa para Backends
        │                                                   │
        ▽ (Isolado da Rede Web)                             ▽
       N/A                                      ┌───────────o───────────┐
                                                │                       │
                                             [Loki]  [Mimir]  [Tempo]   │
                                                │       │        │      │
                                                └───────o────────┘      │
                                                        ▽               │
                                                    [Grafana] ◀─────────┘
                                                (Porta 3000 Exposta)
```

### 1. Alloy Gateway (O Hub Central)
Roda de forma comum e segura na Docker Engine. Contém nativamente os blocos `otelcol.processor`.
Sua responsabilidade principal é amansar as requisições OpenTelemetry:
*   **Memory Limiter:** Caso haja um surto/DDoS interno, ele passa a descartar dados ao invés de derrubar a Stack.
*   **Batch:** Aglomera milhares de chamadas HTTP curtas por 5 segundos antes de atirá-las aos BDs, reduzindo exaustão de IOPS e RAM do banco de dados Mimir/Tempo/Loki.
*   **Tail Sampling:** Avalia *traces* a posteriori e filtra com inteligência — retém erros e lentos, descarta os 95% de chamadas saudáveis repetitivas (Veja `TRACES.md`). **Atenção: este filtro atua exclusivamente em traces (spans OTLP). Logs e métricas passam diretamente para o Batch sem amostragem.**

> **HTTP Bind (Alloy v1.x):** A partir do Alloy v1.0, o servidor HTTP faz bind padrão em `127.0.0.1:12345` (loopback). O flag `--server.http.listen-addr=0.0.0.0:12345` declarado no `compose.yaml` é obrigatório para que o port mapping do Docker funcione e a UI seja acessível externamente.

### 2. Alloy Agent (O Espião Silencioso)
Contêiner injetado com flag de `privileged: true`. Ele não sabe o que é uma porta web; e o mundo não sabe o que ele é.
Ele espiona `/host/proc` e `/var/log` usando regras _Strict-Whitelist_ e manda os achados pelo túnel interno até o Gateway.

> **Mount Propagation:** O volume `/:/host:ro` usa propagação `rprivate` (padrão Docker), suficiente para leitura de paths fixos já existentes no boot (`/proc`, `/sys`, `/var/log`). Em Linux de produção com systemd, pode-se adicionar `,rslave` para que novos pontos de montagem criados no host **após** o start do container também fiquem visíveis em `/host`. **WSL2 não suporta `rslave`** — o root filesystem do WSL2 é montado como `private`, incompatível com slave propagation. A versão sem propagação é obrigatória em ambiente de desenvolvimento.

---

## Imagens Distroless (Backends)

Loki, Mimir e Tempo utilizam imagens **distroless** — contêm apenas o binário do serviço, sem shell (`/bin/sh`), sem `wget`, sem utilitários de sistema. Isso implica:

*   **Healthchecks Docker desabilitados:** O mecanismo padrão `CMD-SHELL` falha com `exec: "/bin/sh": stat /bin/sh: no such file or directory`. Por isso os três backends têm `healthcheck: disable: true` no `compose.yaml`.
*   **`depends_on` por `service_started`:** Grafana e Alloy dependem dos backends via lista simples (sem `condition: service_healthy`), pois não há healthcheck para aguardar.
*   **Verificação de saúde alternativa:** Use a API HTTP interna de cada serviço via container auxiliar na rede `lgtm`:
    ```bash
    docker run --rm --network lgtm curlimages/curl:latest -s http://loki:3100/ready
    docker run --rm --network lgtm curlimages/curl:latest -s http://mimir:9009/ready
    docker run --rm --network lgtm curlimages/curl:latest -s http://tempo:3200/ready
    ```

---

## O Conceito "Zero Trust" Portuário

* **Bancos de dados são mudos:** Os portões de entrada nativos (`3100`, `9009`, `3200`) do Loki, Mimir e Tempo **não estão mapeados** no Docker Compose. Nenhum script ou atacante rodando no Host da máquina local pode alcançar os bancos. Eles existem estritamente dentro da sub-rede fictícia `lgtm`, atendendo unicamente ao Gateway e ao Grafana.
* **Leitura Única:** O Grafana é o ponto soberano de _Read_. Ele detém todas as credenciais internas. Em termos de "Ver dados", apenas a porta `3000` é real.

---
🔙 Voltar: [README Principal](README.md)
