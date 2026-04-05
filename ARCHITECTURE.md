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
*   **Memory Limiter:** Caso haja um surto/DDoS interno, ele passa a descartar traces ao invés de derrubar a Stack.
*   **Batch:** Aglomera milhares de chamadas HTTP curtas por 5 segundos antes de atirá-las aos BDs, reduzindo exaustão de IOPS e RAM do banco de dados Mimir/Tempo.
*   **Tail Sampling:** Avalia traços *a posteriori* e descarta dezenas de milhares de logs sadios inúteis (Veja `TRACES.md`).

### 2. Alloy Agent (O Espião Silencioso)
Contêiner injetado com flag de `privileged: true`. Ele não sabe o que é uma porta web; e o mundo não sabe o que ele é.
Ele espiona `/host/proc` e `/var/log` usando regras _Strict-Whitelist_ e manda os achados pelo túnel interno até o Gateway.

---

## O Conceito "Zero Trust" Portuário

* **Bancos de dados são mudos:** Os portões de entrada nativos (`3100`, `9009`, `3200`) do Loki, Mimir e Tempo **não estão mapeados** no Docker Compose. Nenhum script ou atacante rodando no Host da máquina local pode alcançar os bancos. Eles existem estritamente dentro da sub-rede fictícia `lgtm`, atendendo unicamente ao Gateway e ao Grafana.
* **Leitura Única:** O Grafana é o ponto soberano de _Read_. Ele detém todas as credenciais internas. Em termos de "Ver dados", apenas a porta `3000` é real.

---
🔙 Voltar: [README Principal](README.md)
