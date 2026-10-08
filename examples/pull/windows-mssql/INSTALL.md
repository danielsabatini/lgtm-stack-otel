# Coleta Remota — Servidores Windows + SQL Server Legados (windows_exporter)

Para servidores Windows com SQL Server onde **não é possível instalar o agente
OpenTelemetry** e há o `windows_exporter` com o coletor `mssql`. O `otel-agent`
da stack faz o scrape (`:9182`), converte as métricas para o **mesmo formato do
agente** (`system.*` e `sqlserver.*`, OTel Semantic Conventions) com a
identidade OpenTelemetry do servidor e envia ao `otel-gateway` — o Gateway
continua recebendo só OTLP, sem conversão.

| Aspecto | Pull legado (este guia) | Agente OpenTelemetry ([push/windows-mssql](../../push/windows-mssql/INSTALL.md)) |
|---|---|---|
| Métricas de SO | `system.*` (convertidas de `windows_*`) | `system.*` (mesmos nomes do Linux) |
| Métricas do SQL Server | `sqlserver.*` (convertidas do coletor mssql) | `sqlserver.*` (receiver nativo) |
| Dashboard | **Windows + SQL Server Hosts** (o mesmo do agente) | **Windows + SQL Server Hosts** |
| Instância / banco | `sqlserver.instance.name` / `db.namespace` | `service.instance.id` / `db.namespace` |
| Event Log | ❌ | ✅ |

> **Prefira o agente** sempre que possível; use o pull como transição.

Validado com windows_exporter **0.31.8** em Windows Server 2022 com duas
instâncias de SQL Server (`MSSQLSERVER` e `MSSQL2`).

---

## 1. No servidor Windows (legado)

### 1.1 Instalar o windows_exporter com o coletor mssql

Mesmo procedimento de [examples/pull/windows](../windows/INSTALL.md) (seção
1.1, com verificação de checksum), acrescentando `mssql` aos coletores:

```powershell
Start-Process msiexec.exe -Wait -ArgumentList "/i `"$msi`" /qn /norestart ENABLED_COLLECTORS=cpu,logical_disk,memory,net,os,system,pagefile,mssql LISTEN_PORT=9182"
```

O coletor `mssql` lê os contadores de desempenho de **todas** as instâncias do
servidor, sem credencial de banco.

### 1.2 Restringir o acesso à porta 9182 (obrigatório)

Igual à seção 1.2 de [examples/pull/windows](../windows/INSTALL.md): liberar a
`9182` somente para o IP do servidor da stack.

---

## 2. No servidor da stack LGTM

```bash
cp examples/pull/windows-mssql/windows-mssql-hosts.yaml otel-agent/pull.d/
```

Edite `otel-agent/pull.d/windows-mssql-hosts.yaml` — um item por servidor:

```yaml
- targets: ["10.0.0.41:9182"]
  labels:
    host_name: "srv-sql-01"
    deployment_environment_name: prd
    cloud_provider: mgc
    cloud_region: br-se1
    cloud_availability_zone: a
```

```bash
docker compose restart otel-agent
docker logs otel-agent 2>&1 | grep -E "carregando coleta pull|Everything is ready"
```

> Use `windows-mssql-hosts.yaml` **ou** `windows-hosts.yaml` para um mesmo
> servidor, não os dois: ambos coletam as métricas de SO.

---

## 3. O que é coletado (Política Lean)

- **SO:** mesma lista do [pull Windows](../windows/INSTALL.md) (conferida pelo script de consistência).
- **SQL Server:** 13 métricas do coletor `mssql`, convertidas para `sqlserver.*` (`*_mssql_semconv` em `otel-agent/pull-semconv.yaml`) com o formato do receiver do agente — validado contra o agente no mesmo servidor:

| windows_exporter (mssql) | OpenTelemetry (`sqlserver.*`) |
|---|---|
| `genstats_user_connections`, `genstats_blocked_processes` | `user.connection.count`, `processes.blocked` |
| `bufman_page_life_expectancy_seconds` | `page.life_expectancy` |
| `bufman_page_reads` / `page_writes` (cumulativos) | `page.operation.rate{type}` (por segundo) |
| `databases_transactions`, `sqlstats_batch_requests`, `sqlstats_sql_(re)compilations` | `transaction.rate`, `batch.request.rate`, `batch.sql_(re)compilation.rate` |
| `locks_deadlocks`, `locks_lock_waits` (por tipo de recurso) | `deadlock.rate`, `lock.wait.rate` (total da instância) |
| `databases_log_used_percent`, `databases_log_growths` | `transaction_log.usage`, `transaction_log.growth.count` |

Cada instância vira uma identidade própria, como no agente (`service.name=mssql`,
`service.instance.id=<host>\<instância>`). Sem equivalente calculável: hit ratio
do buffer cache e tempo médio de lock (exigem divisão entre métricas).

Os labels do coletor viram atributos da OTel Semantic Conventions, iguais aos
do template push:

| windows_exporter | OpenTelemetry |
|---|---|
| `mssql_instance` | `sqlserver.instance.name` |
| `database` | `db.namespace` |

Bancos internos ocultos (`mssqlsystemresource`, `model_msdb`,
`model_replicatedmaster`) são descartados.

Referência validada: **76 séries por servidor** (2 instâncias de SQL Server),
contra ~1.650 expostas pelo windows_exporter.

---

## 4. Validação

```bash
H="srv-sql-01"
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"up\", \"host.name\"=\"$H\"}"
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=count by (\"sqlserver.instance.name\", \"db.namespace\") ({\"sqlserver.transaction_log.usage\", \"host.name\"=\"$H\"})"
```

No Grafana: dashboard **Hosts + Database → Windows + SQL Server Hosts**.

---

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| `up = 0` | Firewall do Windows, serviço `windows_exporter` parado ou IP errado |
| Sem métricas `sqlserver.*` | Coletor `mssql` ausente no `ENABLED_COLLECTORS` da instalação |
| Template não carregado | Arquivo precisa ter extensão `.yaml` em `otel-agent/pull.d/`; reinicie o `otel-agent` |

---
🔙 Voltar: [README Principal](../../../README.md)
