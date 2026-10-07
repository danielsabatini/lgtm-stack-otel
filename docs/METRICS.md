# Métricas (Mimir e OpenTelemetry)

Este documento cobre somente a política de métricas da stack.

## Endpoints de Ingestão

Toda métrica entra na stack em OTLP pelo OTel Gateway (portas 4317/4318) e é gravada no Mimir pelo endpoint OTLP nativo. Não há ingestão Prometheus `remote_write`.

Para consultar as portas exatas e o roteamento de rede, consulte a matriz oficial em:
👉 **[ARCHITECTURE.md (Fronteiras de Rede)](ARCHITECTURE.md)**

## OTLP Nativo e Semântica OpenTelemetry

Métricas que chegam ao Gateway (sempre OTLP, portas 4317/4318) são gravadas no Mimir pelo endpoint OTLP nativo (`otelcol.exporter.otlphttp "mimir"` → `http://mimir:9009/otlp/v1/metrics`), **sem conversão para o padrão Prometheus**. Os nomes de métricas e de atributos são preservados exatamente como na [OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) (bloco `limits` de `mimir/mimir.yaml`):

| Configuração (`mimir.yaml`) | Efeito |
|---|---|
| `name_validation_scheme: utf8` + `otel_translation_strategy: NoTranslation` | Nome da métrica e dos labels com pontos, sem sufixos `_total`/`_seconds` (ex.: `http.server.request.duration`). |
| `otel_convert_histograms_to_nhcb: true` | Histogramas OTel viram *native histograms* (uma série por histograma, sem `_bucket`/`_sum`/`_count`). |
| `promote_otel_resource_attributes` | `service.name`, `service.namespace`, `service.version`, `service.instance.id`, `deployment.environment.name`, `host.name`, `cloud.provider`, `cloud.region` e `cloud.availability_zone` viram labels em **toda** série (sem `join` com `target_info`). |
| `otel_keep_identifying_resource_attributes` / `otel_promote_scope_metadata` | Mantém `job`/`instance` derivados (spec de compatibilidade OTel↔Prometheus) e o instrumentation scope como `otel_scope_name`/`otel_scope_version`. |
| `max_global_exemplars_per_user: 100000` | Habilita exemplars (link métrica → trace). |

Como consultar (PromQL com nomes UTF-8 — nome e labels com ponto vão entre aspas):

```promql
sum by ("service.name") (rate({"http.server.request.count", "deployment.environment.name"="prd"}[5m]))
histogram_quantile(0.95, sum by ("service.name") (rate({"http.server.request.duration"}[5m])))
```

Verificação rápida (rede interna `lgtm`):

```bash
docker run --rm --network lgtm curlimages/curl -s http://mimir:9009/metrics \
  | grep 'cortex_request_duration_seconds_count{.*route="otlp_v1_metrics"'
```

> **Origem das métricas:** no agente OpenTelemetry (`examples/push/linux`), as métricas de host vêm do receiver `host_metrics` com os nomes da OTel Semantic Conventions (`system.cpu.time`, `system.memory.usage`, `system.filesystem.usage`...) e as métricas HTTP do OBI (`http.server.request.duration`...). Os atributos do `host_metrics` seguem a versão emitida pelo receiver (`state`, `direction`, `device`), pois as system semantic conventions estão em *Development* e a especificação orienta não adotar breaking changes antes de estabilizar. No servidor da stack, o `otel-agent` coleta também as métricas de containers via `docker_stats` (`container.cpu.usage.total`, `container.cpu.throttling_data.*`, `container.memory.usage.total`/`limit`, `container.network.io.usage.rx_bytes`/`tx_bytes`), identificadas pelo label `container.name` (promovido no Mimir — sem ele as séries de containers diferentes se misturariam). Os templates `.alloy` ainda não migrados usam `remote_write` para a porta 9999, que **não existe mais** no Gateway — esses envios falham até a migração (ver [ROADMAP.md](../ROADMAP.md)).
>
> **Bancos de dados:** no servidor MySQL (`examples/push/linux-mysql`), o receiver nativo `mysql` substitui o `mysqld_exporter`: ~38 séries por instância (`mysql.server.healthy`, `mysql.threads`, `mysql.query.count`, `mysql.query.slow.count`, `mysql.row_operations`, `mysql.row_locks`, `mysql.buffer_pool.*`, `mysql.innodb.redo_log.checkpoint.age`, `mysql.tmp_resources`...), todas habilitadas explicitamente. `mysql.table.io.wait.*` e `mysql.index.io.wait.*` vêm ligadas por padrão no receiver com uma série por tabela/índice e ficam **desligadas**.
>
> **PostgreSQL** (`examples/push/linux-pgsql`): o receiver nativo `postgresql` substitui o `postgres_exporter`, sempre com o feature gate `receiver.postgresql.useOTelSemconv` (Alpha): um resource por servidor e o banco no atributo `db.namespace` de cada série — sem o gate, o banco fica só no resource e as séries de bancos diferentes se misturam no Mimir. Apenas métricas no nível de banco (~14 séries por banco: `postgresql.backends`, `connection.max`, `commits`, `rollbacks`, `tup_*`, `deadlocks`, `temp.io`, `blks_hit`/`blks_read`, `db_size`, `bgwriter.checkpoint.count`); as métricas por tabela/índice, ligadas por padrão no receiver, ficam **desligadas**.
>
> **Servidores legados (pull, `examples/pull/linux`):** o `otel-agent` faz o scrape do `node_exporter` remoto e converte para OTLP; os nomes continuam `node_*` (sem equivalência 1:1 com `system.*`), com a identidade OpenTelemetry por alvo (`host.name`, `deployment.environment.name`, `cloud.*`), `job=node-exporter` e `up`. Mesma allowlist Lean do template legado: ~64 séries por servidor (contra ~1.555 expostas pelo `node_exporter`); as séries sintéticas `scrape_*` são descartadas.
>
> **DBaaS MySQL (pull, `examples/pull/linux-dbaas-mysql`):** o `otel-agent` coleta os dois endpoints expostos pelo serviço (`:8080/node/metrics` e `:8080/mysql/metrics`) com jobs `node-exporter` e `mysqld-exporter` e a mesma identidade por instância; o resource do banco recebe `db.system.name=mysql`. Allowlist de SO idêntica à do pull Linux (conferida pelo script de consistência) e 14 métricas `mysql_*` (16 séries com `up`), contra ~3.000 expostas pelo mysqld_exporter.
>
> **DBaaS PostgreSQL (pull, `examples/pull/linux-dbaas-pgsql`):** mesmo modelo, com os endpoints `:8080/node/metrics` e `:8080/postgres/metrics` (jobs `node-exporter` e `postgres-exporter`, `db.system.name=postgresql`). O label `datname` do postgres_exporter vira `db.namespace` (mesma dimensão do template push `linux-pgsql`); os bancos internos `template0`/`template1` e o label `server` (caminho do socket) são descartados. Referência: 44 séries de banco com 2 bancos de aplicação, contra 597 expostas.

## Política de Coleta (Lean Agent Metrics)

Diferente do padrão de mercado que coleta centenas de métricas irrelevantes, nossa arquitetura utiliza uma política de **Explicit Whitelisting (Allowlist)** via `metric_relabel` com a ação `keep`.

O _Node Exporter_ original pode gerar até **1400 séries ativas**. Em nossa stack, filtramos agressivamente na origem para persistir apenas o que é visualizado nos Dashboards.

### Estratégia de Filtragem:
- **Agente OpenTelemetry:** cada scraper e cada métrica do `host_metrics` é habilitada explicitamente (`metrics: <nome>: { enabled: true|false }`); dispositivos (`loop`, `ram`, `dm-*`), pseudo-filesystems e interfaces virtuais são excluídos; o OBI exporta só `features: [application]`; o self-monitoring usa `level: basic`. Referência: ~66 séries `system.*` por host Linux.
- **Templates `.alloy` legados:** o filtro ocorre via `metric_relabel` `keep` no agente antes de enviar o dado pela rede.
- **Gateway:** nunca filtra nem transforma — só repassa o que o agente decidiu coletar.

O resultado é um Mimir _Lean_ operando com **80% a 90% de economia de disco** em comparação com coletas não filtradas.

## Labels

Todos os hosts são identificados exclusivamente pelo label **`instance`**. O label `nodename` **não é utilizado** para evitar duplicidade de cardinalidade — `instance` e `nodename` carregariam o mesmo valor, dobrando o custo de séries sem benefício analítico.

| Label | Valor | Origem |
|---|---|---|
| `job` | `node-exporter` | Injetado pelo `prometheus.relabel` no Alloy Agent |
| `instance` | `$HOSTNAME` (ex: `code`) | Injetado pelo `prometheus.relabel` via `sys.env("HOSTNAME")` |
| `service_name` | `node-exporter` | Injetado pelo `prometheus.relabel` |

O mesmo padrão se aplica ao cAdvisor. Para política de logs e labels do Loki, consulte [LOGS.md](LOGS.md).

## Retenção

A retenção é definida dinamicamente. Os blocos persistidos obedecem à variável `MIMIR_RETENTION` do arquivo `.env` da stack.

*   Valor Padrão Original: **`30d`**
*   Cortes de blocos velhos ocorrem autonomamente em partições TSDB limitadas.

> **Requisito técnico:** o Mimir inicializa o componente `ruler` mesmo sem regras configuradas. Por isso `mimir.yaml` precisa declarar `ruler_storage` e `ruler.rule_path` com caminhos graváveis.
> ```
> ruler: failed to access directory ./data-ruler/: open .check: permission denied
> ```
> O `mimir.yaml` desta stack já declara os paths absolutos obrigatórios:
> ```yaml
> ruler_storage:
>   backend: filesystem
>   filesystem:
>     dir: /data/ruler
>
> ruler:
>   rule_path: /data/ruler-temp
> ```

## Dimensionamento (Sizing)

Para cálculos de projeção de disco, cardinalidade real por host e cenários de exemplo, consulte o documento central de capacidade:

👉 **[SIZING.md](SIZING.md)**

## 📋 Padrão de Descrições de Painéis e Métricas nos Dashboards

Toda métrica e painel criado ou mantido nos dashboards Grafana deste repositório **deve obrigatoriamente** conter uma descrição estruturada no campo `Description` (o tooltip `(i)` do painel).

O objetivo é garantir que **qualquer operador, desenvolvedor ou suporte (mesmo com pouco conhecimento prévio do serviço)** compreenda instantaneamente o que a métrica significa, saiba avaliar se o valor está saudável e tenha comandos concretos para iniciar a resolução em caso de incidente.

### Estrutura Obrigatória em 3 Blocos:

1. **O que é (Definição Simples e Direta):**
   * Explicação objetiva do que o gráfico/card mede, **em linguagem acessível** e contextualizada.
   * Evite jargões herméticos de protocolo; prefira exemplos práticos do dia a dia (ex: *"Consultas de serviços internos da nuvem"* em vez de *"Zona ne1.cloud.internal"*).
2. **• O que observar (Sinais Vitais, Padrões e Thresholds):**
   * O comportamento normal e esperado da métrica.
   * Thresholds e limites numéricos claros (ex: *"< 16 ms (Verde), > 32 ms (Vermelho)"*, *"deve permanecer estritamente em 0"*).
   * O impacto real nas aplicações clientes caso o valor desvie do padrão.
3. **• Ação em caso de problema (Resolução e Mitigação):**
   * Comandos reais e objetivos para verificação e diagnóstico (`journalctl`, `systemctl`, `ping`, `dig`, `etcdctl`).
   * Passos de mitigação imediatos e caminhos de arquivos de configuração relevantes.

### Template Canônico:

```text
<O que a métrica mede de forma simples, clara e contextualizada>.
• O que observar: <Valores e comportamento esperado, limites de alerta/thresholds e impacto no cliente>.
• Ação em caso de problema: <Comandos de verificação imediata, testes de conectividade e passos de mitigação>.
```

### Exemplos Reais de Referência:

**1. Painel de Latência (Pilar Health):**
> *Tempo de resposta percebido por 99% das consultas de serviços internos da nuvem (bancos de dados, VMs e nomes *.cloud.internal).*
> *• O que observar: Deve responder em menos de 16 ms (Verde). Valores entre 16 ms e 32 ms indicam lentidão e acima de 32 ms (Vermelho) indicam lentidão crítica para os sistemas internos.*
> *• Ação em caso de problema: A lentidão geralmente está no banco etcd. Verifique a aba 'etcd > Diagnostics' abaixo para ver a velocidade de gravação em disco do etcd.*

**2. Painel de Capacidade de Memória (Pilar Capacity):**
> *Quantidade real de memória RAM física consumida exclusivamente pelo processo do CoreDNS em cada servidor.*
> *• O que observar: Deve ficar estável entre 50 MB e 150 MB. Se a linha subir continuamente sem nunca parar, indica vazamento de memória (memory leak).*
> *• Ação em caso de problema: Verifique se o cache não está configurado com tamanho excessivo ou se há plugins com falha e reinicie o serviço com 'sudo systemctl restart coredns'.*

**3. Painel de Diagnóstico de Descarte (Pilar Diagnostics):**
> *Quantidade de nomes que foram jogados fora da memória antes do tempo porque a gaveta de cache encheu (limite de 10.000 registros atingido).*
> *• O que observar: Deve ficar próximo de zero. Se a taxa estiver alta e constante, o CoreDNS está descartando dados úteis e tendo que buscar tudo de novo, gerando lentidão desnecessária.*
> *• Ação em caso de problema: Aumente o tamanho do cache no '/etc/coredns/Corefile' (mude 'cache 30' para 'cache 30 { success 50000 denial 25000 }') e recarregue com 'sudo systemctl reload coredns'.*

---
🔙 Voltar: [README Principal](../README.md)
