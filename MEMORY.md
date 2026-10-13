# LGTM Stack — Estado Operacional

## Resumo do Estado Atual

- **Stack 100% OpenTelemetry (2026-10-07):** Alloy e Beyla removidos. `otel-gateway` e `otel-agent` em OpenTelemetry Collector Contrib 0.162.0; traces/métricas HTTP via OBI v0.14.0. Backends (Mimir 3.2.1, Loki 3.7.8, Tempo 3.1.0, monolito single-tenant) recebem só OTLP, gravado pelo Gateway, cada um com o seu sinal.
- **Todos os templates de `examples/` migrados para YAML do Collector e validados em máquinas reais:** push `linux`, `linux-mysql`, `linux-pgsql` (VM Debian 13), `windows`, `windows-mssql` (Windows Server 2022, 2 instâncias SQL Server); pull `linux`, `linux-dbaas-mysql`, `linux-dbaas-pgsql` (DBaaS Magalu Cloud), `dns` (3 nós CoreDNS/etcd), `windows`, `windows-mssql` (windows_exporter 0.31.8).
- **Auditoria de docs e diagramas** (pós-migração) concluída: docs alinhadas às configs, diagramas regenerados, governança remapeada para `BOOTSTRAP.md`.

## Pendências

- **Dashboards:** gerados por `artifacts/dashboards/` (`python3 artifacts/dashboards/build.py` regenera os 7 e verifica a metodologia); unificados por tipo de servidor e em conformidade com `docs/OBSERVABILITY-METHODOLOGY.md`. Próximos: Service Graph (OBI); depois alertas como código, release (merge dev→main + tag) e troca das senhas dos hosts de teste.
- **Service Graph:** feature `application_service_graph` do OBI desligada (Lean); avaliar junto com os dashboards.
- **Regras de alerta** como código, depois dos dashboards.
- Hosts de teste: Windows com o `windows-mssql` atual (agente reabilitado); VM Debian com o `linux-pgsql` atual (o `linux-mysql` foi validado antes e está desligado — só um template por vez no mesmo serviço).

## Decisões Ativas / Restrições (Referência Rápida)

- *Pull = mesmo formato do push*: exporters coletados pelo `otel-agent` são convertidos para a OTel Semantic Conventions pelos processors de `otel-agent/pull-semconv.yaml` (validado contra o agente no mesmo servidor). Sem equivalente: load/disco ocupado no Windows, hit ratio/lock wait médio do SQL Server; CoreDNS/etcd mantêm nomes dos exporters.
- *Origem correta*: o dado sai do agente já em OTLP com a OTel Semantic Conventions; o Gateway não converte (só `memory_limiter`, tail sampling e `batch`). Servidores legados (pull) são coletados pelo `otel-agent` da stack via `otel-agent/pull.d/*.yaml` (não versionados), sem `resource_detection`.
- *Identidade*: `OTEL_RESOURCE_ATTRIBUTES` + detector `system` com `override: true` no agente; no pull, labels `host_name`/`deployment_environment_name`/`cloud_*` declarados por alvo. Atributos que identificam séries precisam estar em `promote_otel_resource_attributes` do Mimir (ex.: `container.name`).
- *Política Lean*: coletar e armazenar o mínimo necessário — cada métrica e fonte de log habilitada explicitamente, severidade filtrada na origem. Espelhos verificados por `artifacts/scripts/check-examples-consistency.py`.
- *Sampling*: exclusivamente no Gateway (erros, > 1 s e 5% dos OK). Troubleshooting: `otelcol_receiver_accepted_spans` subindo com `otelcol_processor_tail_sampling_global_count_traces_sampled` parado indica tail sampling travado; `sampling_traces_on_memory` igual a `new_trace_id_received` é NORMAL.
- *OBI*: usuário dedicado `obi` com capabilities eBPF, `context_propagation: headers`; bpffs liberado via `ExecStartPre=+`.
- *ADRs*: em `decisions/` na raiz — exceção de projeto ao `BOOTSTRAP.md` §1.3 (registrada no `PROJECT.md`).

## Bloqueios Atuais

Nenhum.
