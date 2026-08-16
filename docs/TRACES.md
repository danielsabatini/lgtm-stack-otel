# Traces (Tempo e OTLP)

> **Referência Técnica:** Este documento estabelece a política de ingestão de rastreamento distribuído (Distributed Tracing), auto-instrumentação eBPF e estratégias de amostragem (Tail Sampling) no Grafana Tempo.

---

## 1. Introdução

O rastreamento distribuído (*Distributed Tracing*) é o sinal de observabilidade que permite acompanhar a jornada de uma requisição ponta a ponta à medida que ela atravessa múltiplos microsserviços, filas e bancos de dados. 

Na LGTM Stack, o Grafana Tempo atua como o backend central de armazenamento de traces, recebendo dados no padrão aberto **OpenTelemetry (OTLP)** e correlacionando spans diretamente com métricas e logs.

---

## 2. Objetivo

1. **Permitir Rastreamento Ponta a Ponta:** Mapear a cascata de chamadas e identificar com precisão em qual etapa ocorreu a lentidão ou erro.
2. **Suportar Auto-Instrumentação eBPF:** Permitir a geração automática de traces HTTP e gRPC sem necessidade de alterar o código-fonte das aplicações.
3. **Otimizar Armazenamento com Tail Sampling:** Garantir a retenção de 100% dos erros e requisições lentas, descartando repetições desnecessárias de chamadas rápidas com sucesso.

---

## 3. Endpoints e Ingestão OTLP

As aplicações podem enviar traces apontando seus exporters OpenTelemetry diretamente para o **Alloy Gateway**:
* **Porta 4317 (gRPC):** Protocolo OTLP de alta performance.
* **Porta 4318 (HTTP):** Protocolo OTLP via HTTP/JSON.

---

## 4. Coleta Automática via Beyla eBPF (Hosts Linux)

Em servidores Linux onde não é viável alterar o código das aplicações para inserir SDKs do OpenTelemetry, a stack suporta a auto-instrumentação via **Grafana Beyla (`beyla.ebpf`)**:
* **Zero Código:** Inspeciona chamadas HTTP, HTTPS e gRPC diretamente no nível do kernel Linux via eBPF.
* **Métricas RED Automáticas:** Gera automaticamente métricas de taxa de requisições, erros e duração (`traces_spanmetrics_*`) no Mimir.
* **Guia de Instalação:** Consulte o guia em [examples/linux/INSTALL.md](../examples/linux/INSTALL.md#51-traces-beyla-ebpf--opcional).

---

## 5. Estratégia de Amostragem Inteligente (Tail Sampling)

Em ambientes de alta carga, armazenar 100% de todas as requisições bem-sucedidas geraria custos astronômicos de armazenamento sem benefício analítico real. 

O Alloy Gateway aplica o padrão **Tail Sampling** diretamente na memória antes de persistir no Tempo:

1. **Keep-Errors (100% Retido):** Guarda **todas as requisições** onde qualquer span falhou ou retornou erro (`HTTP 5xx`).
2. **Keep-Slow (100% Retido):** Guarda **todas as requisições** cuja duração total ultrapassou **1000 ms** (1 segundo), permitindo diagnosticar gargalos de performance.
3. **Drop Sample-OK (95% Descartado):** Para as requisições rápidas e bem-sucedidas restantes (`HTTP 200 OK`), retém apenas uma amostra estatística de **5%**, descartando os 95% restantes de chamadas idênticas.

---

## 6. Geração de Métricas e Grafo de Serviços (Service Graph)

O componente `metrics_generator` do Grafana Tempo processa os spans ingeridos em tempo real e alimenta o Mimir com:
* **Service Graph:** Grafo de topologia visual no Grafana mostrando as conexões e dependências entre microsserviços.
* **Span Metrics (Métricas RED):** Métricas de taxa de chamadas (`traces_spanmetrics_calls_total`) e histogramas de latência por rota HTTP.

---

## 7. Retenção e Armazenamento

A retenção dos blocos de traces é controlada pela variável `TEMPO_RETENTION` no arquivo `.env` (padrão: `336h` / 14 dias).

Para cálculos de impacto em disco e dimensionamento, consulte [SIZING.md](SIZING.md).

---

## 8. Governança e Referências

* Para a metodologia de correlação entre Métricas, Logs e Traces, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para a topologia de rede e portas do Gateway, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](../README.md)
