# Métricas (Mimir e OpenTelemetry)

> **Referência Técnica:** Este documento é a fonte única da política de métricas da stack: como as métricas entram, como são gravadas no Mimir com a semântica OpenTelemetry, como cada série é identificada, o que é coletado (Política Lean) e por quanto tempo é guardado.

---

## 1. Introdução

Toda métrica da LGTM Stack chega em **OTLP** ao `otel-gateway` e é gravada no Mimir pelo endpoint OTLP nativo, **sem conversão para o padrão Prometheus**. Os nomes das métricas e dos atributos seguem a [OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) — por isso uma consulta usa `{"system.cpu.time", "host.name"="web-01"}` em vez de `node_cpu_seconds_total{instance="web-01"}`.

Métricas sem filtro crescem de forma descontrolada (um `node_exporter` expõe ~1.500 séries por host, um `mysqld_exporter` ~3.000). A stack coleta **só o necessário**, com cada métrica declarada explicitamente na origem.

---

## 2. Objetivo

1. **Gravar com semântica OpenTelemetry:** nomes e atributos idênticos aos da especificação, consultáveis diretamente no Mimir.
2. **Identificar cada série sem ambiguidade:** host, ambiente, cloud, serviço, instância e banco sempre presentes como labels.
3. **Coletar o mínimo necessário (Política Lean):** cada métrica habilitada explicitamente, com referência de séries por tipo de servidor.
4. **Padronizar a leitura nos dashboards:** descrição obrigatória de cada painel.

---

## 3. Caminho de Ingestão

```text
agente (host_metrics, receivers de banco, OBI)  ─┐
otel-agent (pull de exporters legados)          ─┼─ OTLP ──> otel-gateway :4317/:4318 ──> Mimir /otlp/v1/metrics
aplicações instrumentadas                        ─┘
```

* O `otel-gateway` não filtra, não renomeia e não converte métricas (`otel-gateway/config.yaml`).
* Não existe ingestão Prometheus `remote_write`. Exporters Prometheus (`node_exporter`, `windows_exporter`, exporters de banco) são coletados pelo `otel-agent` da stack e convertidos **no agente** para o **mesmo formato do push** — nomes, atributos e semântica da OTel Semantic Conventions, iguais aos dos receivers nativos (`otel-agent/pull-semconv.yaml`, seção 7.1). Push e pull são indistinguíveis no Mimir e nos dashboards.
* O Tempo não gera métricas (`metrics_generator` desabilitado): as métricas HTTP/RED vêm do OBI na origem (ver [TRACES.md](TRACES.md)).

Verificação de que só há escrita OTLP no Mimir (rede interna `lgtm`):

```bash
docker run --rm --network lgtm curlimages/curl -s http://mimir:9009/metrics \
  | grep -E 'cortex_request_duration_seconds_count\{.*route="(api_v1_push|otlp_v1_metrics)"'   # só otlp_v1_metrics
```

---

## 4. Armazenamento no Mimir com Semântica OpenTelemetry

Configuração no bloco `limits` de `mimir/mimir.yaml`:

| Configuração | Efeito |
|---|---|
| `name_validation_scheme: utf8` + `otel_translation_strategy: NoTranslation` | Nomes de métricas e labels gravados como na especificação, com pontos e sem sufixos `_total`/`_seconds` (ex.: `http.server.request.duration`). |
| `otel_convert_histograms_to_nhcb: true` | Histogramas viram *native histograms*: uma série por histograma, sem `_bucket`/`_sum`/`_count`. |
| `promote_otel_resource_attributes` | Resource attributes que identificam a origem viram labels em **toda** série (seção 5). |
| `otel_keep_identifying_resource_attributes` / `otel_promote_scope_metadata` | Mantém `job`/`instance` derivados (compatibilidade OTel↔Prometheus) e o instrumentation scope em `otel_scope_name`/`otel_scope_version`. |
| `max_global_exemplars_per_user: 100000` | Habilita exemplars (link métrica → trace, label `trace_id`). |

> **Status:** as opções OTLP do Mimir são marcadas como *experimental* (`mimir -help-all`). Releia as release notes a cada upgrade ([UPGRADE.md](UPGRADE.md)).

### 4.1 Como consultar

Nomes e labels com ponto vão entre aspas (PromQL com nomes UTF-8):

```promql
# Taxa por serviço
sum by ("service.name") (rate({"http.server.request.duration", "deployment.environment.name"="prd"}[5m]))

# Percentil de um native histogram (sem _bucket)
histogram_quantile(0.99, sum by ("host.name") (rate({"coredns_dns_request_duration_seconds"}[5m])))

# Quantidade de observações de um native histogram (no lugar de _count)
histogram_count(rate({"http.server.request.duration"}[5m]))
```

### 4.2 Atributos das métricas de host

O receiver `host_metrics` emite os nomes `system.*` da especificação, mas os atributos na versão que ele implementa (`state`, `direction`, `device`): as *system semantic conventions* estão em *Development* e a especificação orienta as instrumentações a não adotar *breaking changes* antes de estabilizar. Os mesmos nomes valem para **Linux e Windows** — um painel de host serve aos dois sistemas.

---

## 5. Identidade das Séries

A identidade é definida **uma vez no agente** (`OTEL_RESOURCE_ATTRIBUTES` + detector `system`, `override: true`) ou **por alvo** nas coletas pull. No Mimir, os atributos abaixo viram labels de toda série:

| Label | Origem | Exemplo |
|---|---|---|
| `host.name` | detector `system` (agente) ou `host_name` do alvo (pull) | `web-01` |
| `deployment.environment.name` | `OTEL_RESOURCE_ATTRIBUTES` ou alvo | `prd` |
| `os.type` | detector `system` (agente) ou conversão do pull (`otel-agent/pull-semconv.yaml`) | `linux`, `windows` — separa hosts Linux e Windows, que usam os mesmos nomes `system.*` |
| `cloud.provider` / `cloud.region` / `cloud.availability_zone` | `OTEL_RESOURCE_ATTRIBUTES` ou alvo | `mgc` / `br-se1` / `a` |
| `service.name` (`job`) | receiver/agente | `mysql`, `postgresql`, `mssql`, `otel-agent`, `node-exporter` |
| `service.instance.id` (`instance`) | receiver ou agente | `WIN-01\MSSQL2` |
| `service.namespace`, `service.version` | aplicação (OBI/SDK) | — |
| `container.name`, `container.image.name` | `docker_stats` | `loki` |
| `sqlserver.instance.name` | receiver `sqlserver` (agente) ou conversão do pull | `MSSQL2` — filtro de instância nos dashboards |

O `target_info` do self-monitoring de cada agente carrega ainda `os.description` (distribuição e kernel), usado no inventário dos dashboards sem criar séries novas — o Loki descarta esse atributo dos logs (`loki/loki.yaml`).

Atributos que **não** são resource, mas identificam a série, ficam no próprio datapoint: `db.namespace` (banco), `sqlserver.instance.name`, `state`, `device` etc.

> **Consultas:** séries mudam de labels quando um atributo de recurso ou de escopo muda (ex.: upgrade do Collector altera `otel_scope_version`) e, por ~5 min, as duas versões coexistem. Nos dashboards, deduplique com `max by (<dimensões>)` antes de somar (ex.: `sum(max by (state) ({"system.memory.usage", ...}))`).

> **Regra:** todo atributo que identifica a origem de uma série precisa estar em `promote_otel_resource_attributes` **ou** no datapoint. Se ficar só no resource sem promoção, séries de origens diferentes ficam com labels idênticas e se misturam no Mimir. Foi o caso de `container.name` (resolvido com promoção), do banco no PostgreSQL (feature gate `receiver.postgresql.useOTelSemconv`) e da instância/banco no SQL Server (conversão no agente).

---

## 6. Política Lean (Coletar e Armazenar o Mínimo Necessário)

Nada é coletado "por segurança":

* **Agentes OpenTelemetry:** cada métrica é declarada (`metrics: <nome>: { enabled: true|false }`), inclusive as que vêm ligadas por padrão nos receivers. Dispositivos, filesystems e interfaces sem valor operacional são excluídos. O self-monitoring usa `level: basic` e o OBI exporta só `features: [application]`.
* **Coletas pull:** allowlist via `metric_relabel_configs` (`action: keep`) no `otel-agent`; séries sintéticas `scrape_*` descartadas.
* **Gateway:** nunca filtra — só repassa o que o agente decidiu coletar.
* A lista de métricas de host é **idêntica** em todos os agentes Linux/Windows e no `otel-agent`, e as allowlists pull do mesmo exporter são iguais entre templates (`artifacts/scripts/check-examples-consistency.py`).

Para incluir uma métrica nova: habilite-a no template correspondente (e no `otel-agent/config.yaml`, se for de host), rode o script de consistência e, se a cardinalidade subir de forma relevante, atualize [SIZING.md](SIZING.md).

---

## 7. Catálogo por Fonte

Referências medidas nos testes de validação de cada template (detalhes de configuração no `INSTALL.md` de cada um):

| Fonte | Template | Coleta | Nomes | Séries (referência) |
|---|---|---|---|---|
| Host Linux | [push/linux](../examples/push/linux/INSTALL.md) | `host_metrics` | `system.*` | ~67 por host |
| Host Windows | [push/windows](../examples/push/windows/INSTALL.md) | `host_metrics` | `system.*` | ~30 por host |
| Containers do servidor da stack | `otel-agent` | `docker_stats` | `container.*` | 7 por container |
| Aplicações HTTP/gRPC | [push/linux](../examples/push/linux/INSTALL.md) (OBI) | eBPF | `http.server.request.duration`, `http.client.request.duration`, `rpc.server.call.duration` | por serviço/rota |
| MySQL | [push/linux-mysql](../examples/push/linux-mysql/INSTALL.md) | receiver `mysql` | `mysql.*` | ~38 por instância |
| PostgreSQL | [push/linux-pgsql](../examples/push/linux-pgsql/INSTALL.md) | receiver `postgresql` (gate `useOTelSemconv`) | `postgresql.*` + `db.namespace` | ~14 por banco |
| SQL Server | [push/windows-mssql](../examples/push/windows-mssql/INSTALL.md) | receiver `sqlserver` (contadores) | `sqlserver.*` + `db.namespace` | ~25 por instância |
| Host Linux legado | [pull/linux](../examples/pull/linux/INSTALL.md) | `node_exporter` → conversão | `system.*` | ~46 por host |
| Host Windows legado | [pull/windows](../examples/pull/windows/INSTALL.md) | `windows_exporter` → conversão | `system.*` | ~26 por host |
| Windows + SQL Server legado | [pull/windows-mssql](../examples/pull/windows-mssql/INSTALL.md) | `windows_exporter` (mssql) → conversão | `system.*`, `sqlserver.*` + `db.namespace` | ~76 por servidor (2 instâncias) |
| DBaaS MySQL | [pull/linux-dbaas-mysql](../examples/pull/linux-dbaas-mysql/INSTALL.md) | node + mysqld_exporter → conversão | `system.*`, `mysql.*` | ~58 SO + ~33 banco |
| DBaaS PostgreSQL | [pull/linux-dbaas-pgsql](../examples/pull/linux-dbaas-pgsql/INSTALL.md) | node + postgres_exporter → conversão | `system.*`, `postgresql.*` + `db.namespace` | ~58 SO + ~30 banco |
| Cluster DNS (por nó) | [pull/dns](../examples/pull/dns/INSTALL.md) | node → conversão + CoreDNS + etcd | `system.*`, `coredns_*`, `etcd_*` | ~51 + ~61 + ~18 |
| Self-monitoring | gateway e agentes | telemetria interna | `otelcol_*` | ~40–65 por coletor |

### 7.1 Conversão das Coletas Pull (mesmo formato do push)

Os processors compartilhados de `otel-agent/pull-semconv.yaml` (carregado sempre pelo `otel-agent`) convertem cada exporter para os nomes, atributos e a semântica do receiver nativo do agente — validados contra o agente no **mesmo servidor** (valores iguais):

| Exporter | Vira | Destaques da conversão |
|---|---|---|
| `node_exporter` | `system.*` | CPU agregada por `state` (`iowait`→`wait`, `irq`→`interrupt`); memória `used` = MemTotal − MemAvailable e `cached` = Cached + SReclaimable (semântica do gopsutil); filesystem `used`/`free` (disponível)/`reserved`; `os.description` no `target_info` |
| `windows_exporter` | `system.*` | `privileged`→`system`, `dpc` descartado; memória `free` = disponível; `volume`/`nic` → `device` |
| coletor `mssql` | `sqlserver.*` | uma identidade por instância (`service.instance.id` = `<host>\<instância>`); contadores cumulativos → `*.rate` por segundo |
| `postgres_exporter` | `postgresql.*` | `datname` → `db.namespace`; versão em `db.system.version` |
| `mysqld_exporter` | `mysql.*` | contadores *untyped* → Sum; `buffer_pool.usage` clean/dirty; idade do checkpoint do redo |

Subtrações entre métricas (ex.: `used = total − available`) são feitas só com o `metrics_transform`: uma cópia do subtraendo × −1 é combinada (`combine`, `sum`) com o minuendo, preservando as dimensões de cada série.

**Sem equivalente calculável no pull** (painéis ficam sem dados para esses hosts): load average e *disk busy* no Windows; hit ratio e tempo médio de lock do SQL Server (exigem divisão entre métricas); logs e traces (exigem o agente). **Sem OTel Semantic Conventions:** CoreDNS e etcd mantêm os nomes dos exporters.

---

## 8. Retenção

A retenção do Mimir é definida pela variável `MIMIR_RETENTION` do `.env` (padrão **`30d`**), aplicada pelo compactor em `limits.compactor_blocks_retention_period`.

> **Requisito técnico:** o Mimir inicializa o componente `ruler` mesmo sem regras. Por isso `mimir.yaml` declara `ruler_storage` e `ruler.rule_path` com caminhos graváveis (`/data/ruler` e `/data/ruler-temp`). Sem eles a inicialização falha com `ruler: failed to access directory ./data-ruler/: open .check: permission denied`.

---

## 9. Padrão de Descrições de Painéis

Todo painel dos dashboards deste repositório **deve** ter uma descrição estruturada no campo `Description` (o tooltip `(i)`), para que qualquer operador entenda o que a métrica significa, saiba se o valor está saudável e tenha comandos para começar a resolver um incidente.

### 9.1 Estrutura obrigatória em 3 blocos

1. **O que é:** o que o gráfico mede, em linguagem acessível e com exemplo prático (ex.: *"Consultas de serviços internos da nuvem"* em vez de *"Zona ne1.cloud.internal"*).
2. **• O que observar:** comportamento normal, thresholds numéricos (ex.: *"< 16 ms (Verde), > 32 ms (Vermelho)"*) e impacto nas aplicações se o valor desviar.
3. **• Ação em caso de problema:** comandos reais de verificação (`journalctl`, `systemctl`, `ping`, `dig`, `etcdctl`) e passos de mitigação com caminhos de arquivos.

### 9.2 Template canônico

```text
<O que a métrica mede de forma simples, clara e contextualizada>.
• O que observar: <Valores e comportamento esperado, limites de alerta/thresholds e impacto no cliente>.
• Ação em caso de problema: <Comandos de verificação imediata, testes de conectividade e passos de mitigação>.
```

### 9.3 Exemplos de referência

**Latência (pilar Health):**
> *Tempo de resposta percebido por 99% das consultas de serviços internos da nuvem (bancos de dados, VMs e nomes \*.cloud.internal).*
> *• O que observar: Deve responder em menos de 16 ms (Verde). Valores entre 16 ms e 32 ms indicam lentidão e acima de 32 ms (Vermelho) indicam lentidão crítica para os sistemas internos.*
> *• Ação em caso de problema: A lentidão geralmente está no banco etcd. Verifique a aba 'etcd > Diagnostics' abaixo para ver a velocidade de gravação em disco do etcd.*

**Memória (pilar Capacity):**
> *Quantidade real de memória RAM física consumida exclusivamente pelo processo do CoreDNS em cada servidor.*
> *• O que observar: Deve ficar estável entre 50 MB e 150 MB. Se a linha subir continuamente sem nunca parar, indica vazamento de memória (memory leak).*
> *• Ação em caso de problema: Verifique se o cache não está configurado com tamanho excessivo ou se há plugins com falha e reinicie o serviço com 'sudo systemctl restart coredns'.*

**Descarte de cache (pilar Diagnostics):**
> *Quantidade de nomes que foram jogados fora da memória antes do tempo porque a gaveta de cache encheu (limite de 10.000 registros atingido).*
> *• O que observar: Deve ficar próximo de zero. Se a taxa estiver alta e constante, o CoreDNS está descartando dados úteis e tendo que buscar tudo de novo, gerando lentidão desnecessária.*
> *• Ação em caso de problema: Aumente o tamanho do cache no '/etc/coredns/Corefile' (mude 'cache 30' para 'cache 30 { success 50000 denial 25000 }') e recarregue com 'sudo systemctl reload coredns'.*

---

## 10. Governança e Referências

* Topologia, portas e regras de escrita: [ARCHITECTURE.md](ARCHITECTURE.md).
* Projeção de disco e cardinalidade: [SIZING.md](SIZING.md).
* Logs (identidade e Política Lean dos logs): [LOGS.md](LOGS.md).
* Traces e métricas derivadas (OBI, exemplars): [TRACES.md](TRACES.md).
* Dashboards (fluxo GitOps): [DASHBOARDS.md](DASHBOARDS.md).
* Upgrades e breaking changes do Mimir: [UPGRADE.md](UPGRADE.md).

---
🔙 Voltar: [README Principal](../README.md)
