# OpenTelemetry Collector — Instalação em Servidor Windows + SQL Server (Modo Agent)

Guia para monitorar um servidor Windows com **SQL Server** com o agente
OpenTelemetry, enviando tudo em OTLP ao `otel-gateway` da stack — com a
[OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).

O servidor é monitorado como **host + banco** no mesmo agente: o `config.yaml`
deste diretório é o template Windows ([examples/push/windows](../windows/INSTALL.md))
acrescido do SQL Server.

| Sinal | Origem | Nomes |
|---|---|---|
| Métricas de host e Event Log do Windows | igual ao template Windows | `system.*`, `windows-security`, `windows-system`... |
| Métricas do SQL Server | receiver nativo `sqlserver` (contadores de desempenho) | `sqlserver.*`, uma identidade por instância |
| Erros do SQL Server | `windows_event_log` (Application) | `service.name=mssql`, `db.response.status_code` |

**Não exige usuário nem senha do banco:** as métricas vêm dos contadores de
desempenho do Windows, lidos pelo serviço `otelcol-contrib` (conta
`LocalSystem`).

Validado em Windows Server 2022 com **duas instâncias** (`MSSQLSERVER` padrão e
`MSSQL2` nomeada): 25 séries por instância.

---

## 1. Instalar o Collector e definir a identidade

Siga os passos **1 a 3** do guia Windows ([examples/push/windows/INSTALL.md](../windows/INSTALL.md)):
resolução de `lgtm-stack`, MSI oficial com verificação de checksum e variáveis
de ambiente do serviço (`OTEL_RESOURCE_ATTRIBUTES`, `LGTM_GATEWAY_ENDPOINT`).

---

## 2. Declarar as instâncias do SQL Server

Liste as instâncias do servidor:

```powershell
Get-Service | Where-Object Name -match '^MSSQL(SERVER|\$)' | Select-Object Name, Status
# MSSQLSERVER      -> instância padrão
# MSSQL$<NOME>     -> instância nomeada <NOME>
```

No `config.yaml`, mantenha **um receiver por instância** e inclua todos no
pipeline `metrics/sqlserver`:

```yaml
sqlserver/default: &sqlserver_lean   # instância padrão (sem instance_name)
  ...
sqlserver/mssql2:                    # instância nomeada
  <<: *sqlserver_lean
  instance_name: MSSQL2              # nome SEM o prefixo MSSQL$
  computer_name: ${env:COMPUTERNAME}
```

E ajuste os providers do Event Log (um por instância) em
`windows_event_log/sqlserver`:

```xml
*[System[(Provider[@Name='MSSQLSERVER'] or Provider[@Name='MSSQL$MSSQL2']) and (Level=1 or Level=2 or Level=3)]]
```

> O template legado filtrava apenas `MSSQLSERVER` e **perdia os erros das
> instâncias nomeadas**.

---

## 3. Configurar e iniciar

```powershell
$dir = "C:\Program Files\OpenTelemetry Collector"
Copy-Item "<repositorio>\examples\push\windows-mssql\config.yaml" "$dir\config.yaml" -Force

$envs = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\otelcol-contrib").Environment
$envs | ForEach-Object { $k,$v = $_ -split "=",2; [Environment]::SetEnvironmentVariable($k, $v, "Process") }
& "$dir\otelcol-contrib.exe" validate --config "$dir\config.yaml"; "validate: $LASTEXITCODE"   # 0

Restart-Service otelcol-contrib
```

---

## 4. O que é coletado do SQL Server (Política Lean)

Cada métrica é habilitada ou desabilitada explicitamente (coleta a cada 60 s):

| Grupo | Métricas |
|---|---|
| Conexões e carga | `sqlserver.user.connection.count`, `sqlserver.batch.request.rate`, `sqlserver.batch.sql_compilation.rate`, `sqlserver.batch.sql_recompilation.rate` |
| Buffer pool | `sqlserver.page.buffer_cache.hit_ratio`, `sqlserver.page.life_expectancy`, `sqlserver.page.operation.rate` |
| Contenção | `sqlserver.lock.wait.rate`, `sqlserver.lock.wait_time.avg` |
| Por banco (`db.namespace`) | `sqlserver.transaction.rate`, `sqlserver.transaction_log.usage`, `sqlserver.transaction_log.growth.count` |

Conversões feitas no agente (o receiver não tem opção para isso):

| Problema do receiver | Correção no `config.yaml` |
|---|---|
| Todas as instâncias saem com o mesmo `service.instance.id` (`<host>:1433`) — as séries se misturariam no Mimir | `service.instance.id` = `<host>\<instância>` (a padrão vira `MSSQLSERVER`) |
| Nome do banco só no resource (`sqlserver.database.name`) | Movido para o atributo `db.namespace` (OTel Semantic Conventions) |
| Bancos internos ocultos (`mssqlsystemresource`, `model_msdb`, `model_replicatedmaster`) | Descartados |
| Eventos do SQL Server com mensagem vazia (o receiver não renderiza a DLL de mensagens do SQL) | Body montado a partir de `event_data` (`Error: <n> Severity: <s> State: <e> <texto>`) e número do erro em `db.response.status_code` |

> **Não disponível no modo de contadores de desempenho:** memória do SQL
> Server (`sqlserver.memory.usage`), deadlocks (`sqlserver.deadlock.rate`),
> erros de execução (`sqlserver.database.execution.errors`), processos
> bloqueados (`sqlserver.processes.blocked`), I/O por arquivo de banco e
> métricas de índice exigem conexão direta ao banco com usuário de
> monitoramento (`VIEW SERVER PERFORMANCE STATE`). Avalie habilitá-la só se
> forem necessárias.

---

## 5. Verificar o envio de dados

A partir do servidor LGTM (rede interna `lgtm`):

```bash
H="<NOME_DO_COMPUTADOR>"

# Uma série por instância (service.instance.id = <host>\<instância>)
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=count by (\"service.instance.id\") ({__name__=~\"sqlserver[.].+\", \"host.name\"=\"$H\"})"

# Erros do SQL Server
docker run --rm --network lgtm curlimages/curl -sG "http://loki:3100/loki/api/v1/query_range" \
  --data-urlencode "query={host_name=\"$H\", service_name=\"mssql\"}" --data-urlencode 'limit=5'
```

Teste de ponta a ponta (gera um erro registrado no Event Log por instância):

```powershell
sqlcmd -S .          -E -Q "RAISERROR('teste de monitoramento', 16, 1) WITH LOG;"
sqlcmd -S .\MSSQL2   -E -Q "RAISERROR('teste de monitoramento', 16, 1) WITH LOG;"
```

No Grafana: **Explore** → **Mimir** →
`{"sqlserver.page.life_expectancy", "host.name"="<HOST>"}` e **Loki** →
`{service_name="mssql"}`.

---

## Solução de problemas

| Sintoma | Verificação |
|---|---|
| Métricas de uma instância ausentes | `Get-Counter -ListSet 'MSSQL$<NOME>:*'` — o `instance_name` deve ser o nome sem `MSSQL$` |
| Instâncias misturadas no Mimir | O pipeline `metrics/sqlserver` precisa ter `resource_detection` **antes** de `transform/sqlserver` |
| Erros de uma instância não chegam | Provider `MSSQL$<NOME>` ausente no XPath de `windows_event_log/sqlserver` |
| Mensagem de erro vazia | Evento sem `event_data.param4` — consulte o texto completo com `Get-WinEvent -FilterXPath "*[System[EventID=<id>]]"` |
