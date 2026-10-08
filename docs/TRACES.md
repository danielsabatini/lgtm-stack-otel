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

As aplicações podem enviar traces apontando seus exporters OpenTelemetry diretamente para o **OTel Gateway**:
* **Porta 4317 (gRPC):** Protocolo OTLP de alta performance.
* **Porta 4318 (HTTP):** Protocolo OTLP via HTTP/JSON.

---

## 4. Coleta Automática via OBI eBPF (Hosts Linux)

Em servidores Linux onde não é viável alterar o código das aplicações para inserir SDKs do OpenTelemetry, a stack usa o **OBI** ([OpenTelemetry eBPF Instrumentation](https://opentelemetry.io/docs/zero-code/obi/)), serviço `obi` instalado ao lado do Collector do agente:
* **Zero Código:** Inspeciona chamadas HTTP, HTTPS, gRPC e SQL no nível do kernel Linux via eBPF (kernel >= 5.8 com BTF).
* **Propagação de Contexto:** `ebpf.context_propagation: headers` injeta o cabeçalho W3C `traceparent`, costurando serviços que se chamam sob um único `traceID` (validado com a cadeia demo frontend → middleware → backend).
* **Métricas RED Automáticas:** O OBI emite métricas com os nomes da OTel Semantic Conventions (`http.server.request.duration`, `http.client.request.duration`, `rpc.server.call.duration`...), com `http.route`, `http.response.status_code` e `error.type`, contando **100% do tráfego** (antes do tail sampling do Gateway) e com exemplars `trace_id`.
* **Caminho:** OBI → OTLP `127.0.0.1:4317` → Collector do agente (aplica a identidade do host) → OTel Gateway.
* **Guia de Instalação:** Consulte o guia em [examples/push/linux/INSTALL.md](../examples/push/linux/INSTALL.md#6-traces-e-métricas-http-com-obi-opcional).

---

## 5. Estratégia de Amostragem Inteligente (Tail Sampling)

Em ambientes de alta carga, armazenar 100% de todas as requisições bem-sucedidas geraria custos astronômicos de armazenamento sem benefício analítico real. 

O OTel Gateway (`otel-gateway/config.yaml`) aplica o padrão **Tail Sampling** diretamente na memória antes de persistir no Tempo:

1. **Keep-Errors (100% Retido):** Guarda **todas as requisições** onde qualquer span falhou ou retornou erro (`HTTP 5xx`).
2. **Keep-Slow (100% Retido):** Guarda **todas as requisições** cuja duração total ultrapassou **1000 ms** (1 segundo), permitindo diagnosticar gargalos de performance.
3. **Drop Sample-OK (95% Descartado):** Para as requisições rápidas e bem-sucedidas restantes (`HTTP 200 OK`), retém apenas uma amostra estatística de **5%**, descartando os 95% restantes de chamadas idênticas.

---

## 6. Métricas Derivadas de Traces (RED e Service Graph)

O `metrics_generator` do Tempo está **desabilitado**: cada backend armazena apenas o seu sinal e só o Gateway escreve nos backends (ver [ARCHITECTURE.md](ARCHITECTURE.md)). Além disso, o Tempo só enxergaria os traces que sobraram do tail sampling (erros, lentos e 5% dos OK), subestimando a taxa de requisições.

As métricas de taxa, erros e latência passam a ser emitidas **na origem** (OBI no agente, `features: [application]` em `examples/push/linux/obi.yaml`), em OTLP e com a semântica OpenTelemetry, e chegam ao Mimir pelo Gateway como qualquer outra métrica. Exemplars dessas métricas carregam o label `trace_id`, usado pelo datasource Mimir para abrir o trace no Tempo.

> **Service Graph:** as métricas de grafo de serviços do OBI (feature `application_service_graph`) estão **desligadas** pela Política Lean; serão avaliadas junto com a reescrita dos dashboards (ver [ROADMAP.md](../ROADMAP.md)).

Verificação de que o Tempo não escreve métricas:

```bash
docker run --rm --network lgtm curlimages/curl -s http://tempo:3200/metrics \
  | grep -c prometheus_remote_storage_samples_total   # deve ser 0
```

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
