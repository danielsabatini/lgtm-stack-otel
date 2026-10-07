# LGTM Stack — Estado Operacional

## Resumo do Estado Atual

- A stack principal (Gateway + Backend LGTM) foi validada com sucesso, roteando sinais de hosts remotos autenticados.
- Traces distribuídos via Beyla eBPF validados fim-a-fim numa VM Debian com cadeia de microserviços HTTP rodando em cleartext, gerando um único traceID.
- Exemplos de configuração canônica atualizados para refletir as boas práticas validadas (tail sampling deferido, context propagation eBPF por headers e fix no bpffs).

## Trabalho Recente

- **Migração Alloy → OpenTelemetry Collector + OBI (2026-10-07):** backends recebem só OTLP com semântica OTel (Mimir `NoTranslation`/UTF-8); `otel-gateway` e `otel-agent` em otelcol-contrib 0.162.0; template `examples/push/linux` (otelcol-contrib + OBI v0.14.0) validado na VM de teste Debian 13 (`otel-agent`, 192.168.1.42). Pendentes: demais templates de `examples/` e dashboards sobre os nomes OTel.

- **Incidente — Tail Sampling travado no Alloy Gateway (2026-08-20):** Traces do host `lgtm-cliente-1` (192.168.1.61) pararam de chegar ao Tempo mesmo com Beyla, conectividade e demo multi-tier funcionando normalmente. Causa raiz: o processor `otelcol.processor.tail_sampling.apps_traces` (`alloy-gateway/conf.d/003-otlp-gtw-local.alloy`) travou internamente no container `alloy-gateway` (Docker local, 192.168.1.35) — continuava recebendo spans (`otelcol_receiver_accepted_spans_total` subindo) mas nunca liberava a decisão de amostragem para o exportador do Tempo (`otelcol_exporter_sent_spans_total` parado, `sampling_traces_on_memory` == `new_trace_id_received_total`, sem erros de política nem fila cheia — um deadlock silencioso, não backpressure). Sem crash nem OOM do container. Resolvido com `docker compose restart alloy-gateway`; validado fim-a-fim via `/metrics` do gateway e busca no Tempo (`resource.instance="lgtm-cliente-1"`) logo após o restart.
- **Validação de Traces (Beyla):** Demo multi-tier (frontend → middleware → backend) instrumentado na porta via drop-in systemd e `context_propagation = "headers"`.
- **Governança Documental:** Backport das correções do drop-in do Alloy (capabilities e chown via `ExecStartPre`) e do template Alloy local (`config.alloy`) para `examples/push/linux/`.
- **Painel de Traces no Dashboard "Linux Hosts":** Adicionado painel "Distributed Traces" (id=43) usando TraceQL `{ resource.instance =~ "$instance" }`. Corrigido "No data found" causado por tentativa de streaming gRPC do Grafana contra a porta HTTP-only do Tempo (`3200`) — resolvido com `streamingEnabled: {search: false, metrics: false}` em `grafana/provisioning/datasources/datasources.yaml`. Validado via `/api/ds/query`: 18 traces retornados para `lgtm-cliente-1`. Ver `.journal/2026/08/20/0003-corrigir-painel-traces-grafana.md`.
- **Journal Atualizado:** Commits refletidos e estado imutável gravado em `.journal/`.

## Cobertura de Instrumentação (Traces)

- Apenas `lgtm-cliente-1` possui traces reais no Tempo no momento. Hosts `dns-ne1-1`, `dns-ne1-2`, `dns-ne1-3`, `test-host`, `ws1` não têm Beyla instrumentado enviando spans — painel exibirá "No data" para eles corretamente até serem instrumentados.

## Decisões Ativas / Restrições (Referência Rápida)

- *Stack OpenTelemetry*: Gateway = `otel-gateway` (otelcol-contrib, só OTLP, sem conversões); agents = otelcol-contrib (host/journald/docker) + OBI (eBPF). Grafana Alloy só resta nos templates `.alloy` de `examples/` ainda não migrados.
- *Identidade*: única por host, no agent (`OTEL_RESOURCE_ATTRIBUTES` + detector `system`, `override: true`). Atributos que identificam séries precisam estar em `promote_otel_resource_attributes` do Mimir (ex.: `container.name`).
- *eBPF Trace Propagation*: Apenas modo `headers` é endossado por padrão para evitar colisão TC.
- *Sampling*: Exclusivamente deferido ao Gateway. Todos os exports do node devem estar em `always_on`.
- *Troubleshooting de traces "não chegando"*: checar no Mimir as métricas internas do Gateway (`{"service.name"="otel-gateway"}`): `otelcol_receiver_accepted_spans` subindo com `otelcol_processor_tail_sampling_global_count_traces_sampled` parado indica tail sampling travado. **Atenção:** `sampling_traces_on_memory` igual a `new_trace_id_received` é NORMAL (traces ficam em memória após a decisão até serem despejados por `num_traces`); a heurística anterior estava errada. Lembrar também que traces "OK" rápidos são retidos só a 5%.
- *Privilégios*: O OBI roda com usuário dedicado `obi` (unit `obi.service`), as permissões necessárias eBPF são concedidas via capabilities (`AmbientCapabilities`/`CapabilityBoundingSet`) e montagens BPFFS requerem injeção `ExecStartPre=+`.

## Bloqueios Atuais

Nenhum.

## Próximas Ações

O estado da branch `dev` é consistente e seguro para avanço em novos casos de uso de infraestrutura.
