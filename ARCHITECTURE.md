# Arquitetura Física e Lógica (LGTM Stack)

Este documento descreve a topologia da stack e a responsabilidade de cada componente.

## Topologia Geral (O Efeito Gateway-Agent)

Em arquiteturas convencionais, o coletor de telemetria é um processo inflado com poderes de `root` para varrer discos, e simultaneamente exposto à rede web para receber chamadas de APIs. **Nós abolimos essa vulnerabilidade.**

Decidimos separar os pilares do Grafana Alloy:

```text
 🛡️ HOST / KERNEL                                     🕸️ REDE CORPORATIVA / APPs
 ─────────────────                                  ───────────────────────────

  [Alloy Agent] ──────(Push HTTP Interno)────────▶  [Alloy Gateway] ◀──(OTLP Logs/Metrics/Traces)
  - Modo Root                                       - Modo Unprivileged
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

### 1. Alloy Gateway

Roda sem privilégios elevados e é o único ponto de entrada de ingestão.

- Recebe OTLP nas portas `4317` e `4318`.
- Recebe métricas do agent em `9999`.
- Recebe logs do agent em `9998`.
- Encaminha métricas para Mimir, logs para Loki e traces para Tempo.

Detalhes da política de traces ficam em [TRACES.md](TRACES.md).

> **HTTP Bind (Alloy v1.x):** A partir do Alloy v1.0, o servidor HTTP faz bind padrão em `127.0.0.1:12345` (loopback). O flag `--server.http.listen-addr=0.0.0.0:12345` declarado no `compose.yaml` é obrigatório para que o port mapping do Docker funcione e a UI seja acessível externamente.

### 2. Alloy Agent

Roda com `privileged: true` para ler recursos do host e não expõe portas no host.

- Lê `/procfs`, `/sys` e `/rootfs` para métricas do host.
- Lê journald e logs Docker para observabilidade local.
- Envia tudo pela rede interna para o Gateway.

> **Mount propagation:** o volume `/:/rootfs:ro` usa propagação `rprivate` por padrão. Em Linux com systemd, pode-se avaliar `rslave` se for necessário enxergar mounts criados após o start do container. Em WSL2 isso não é compatível.

---

## Backends distroless

Loki, Mimir e Tempo usam imagens distroless.

- Não possuem shell interno.
- Não usam `healthcheck` Docker baseado em `CMD-SHELL`.
- Ficam acessíveis apenas na rede Docker `lgtm`.

Validação operacional e checks de upgrade ficam em [UPGRADE.md](UPGRADE.md).

---

## Isolamento de rede

- Loki, Mimir e Tempo não publicam portas no host.
- Grafana é o ponto de leitura.
- Alloy Gateway é o ponto de ingestão.
- Alloy Agent só fala com o Gateway pela rede interna.

---
🔙 Voltar: [README Principal](README.md)
