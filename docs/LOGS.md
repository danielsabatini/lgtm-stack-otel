# Logs (Loki e OpenTelemetry)

> **Referência Técnica:** Este documento é a fonte única da política de logs da stack: como os logs entram, como são gravados no Loki seguindo o OTel Logs Data Model, as categorias, as fontes coletadas por tipo de servidor (com o filtro de severidade de cada uma) e a retenção.

---

## 1. Introdução

O Loki indexa apenas um conjunto pequeno de **labels** e guarda o texto das mensagens comprimido em blocos (*chunks*) — por isso é barato e rápido, desde que os labels sejam poucos e de baixa cardinalidade.

Na LGTM Stack todo log chega em **OTLP** e segue o [OTel Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/): mensagem no `Body`, severidade em `SeverityText`/`SeverityNumber` e identidade do host e do serviço como *resource attributes*. Cada log recebe ainda uma **categoria funcional** para facilitar a filtragem.

---

## 2. Objetivo

1. **Gravar com semântica OpenTelemetry:** severidade, corpo, identidade e correlação com traces nos campos padrão.
2. **Categorizar:** todo log pertence a uma das 4 categorias canônicas.
3. **Coletar o mínimo necessário:** filtrar severidade e ruído **na origem**, por fonte.
4. **Manter o índice enxuto:** só atributos de identidade de baixa cardinalidade viram labels de índice.

---

## 3. Ingestão e Armazenamento no Loki

Toda a ingestão passa pelo **OTel Gateway** (portas 4317/4318, OTLP), que grava no endpoint OTLP nativo do Loki (`otlp_http/loki` → `http://loki:3100/otlp/v1/logs`, em `otel-gateway/config.yaml`). Não existe API de push do Loki exposta.

| Campo OTel | Onde fica no Loki | Exemplo de consulta |
|---|---|---|
| Resource attributes de identidade: `service.name`, `service.namespace`, `service.instance.id`, `deployment.environment.name`, `host.name`, `cloud.provider`, `cloud.region`, `cloud.availability_zone`, `container.name` | **Labels de índice** (o Loki troca `.` por `_`) | `{service_name="ssh", host_name="web-01"}` |
| `Body` | Texto da linha | `|= "Failed password"` |
| `SeverityText` / `SeverityNumber` | Structured metadata `severity_text` / `severity_number` | `| severity_text="ERROR"` |
| `TraceId` / `SpanId` | Structured metadata `trace_id` / `span_id` | `| trace_id="04d102d4…"` |
| `category` e demais atributos (resource e log record) | Structured metadata | `| category="security"` |

A lista de labels de índice é a padrão do Loki somada a `host.name` e `cloud.provider` (`limits_config.otlp_config` em `loki/loki.yaml`); o atributo `os.description` é descartado (só interessa ao inventário no Mimir). Não promova atributos de alta cardinalidade (IDs de requisição, usuários, IPs) a label de índice.

**Correlação no Grafana** (`grafana/provisioning/datasources/datasources.yaml`): **Log → Trace** pelo derived field `TraceID` (tipo *label*, lê `trace_id` do structured metadata) e **Trace → Logs** pela consulta `{service_name="<service.name do span>"} | trace_id="<trace>"`.

> No Loki os nomes de label usam `_` no lugar de `.` (`host.name` → `host_name`): é uma restrição do próprio Loki, sem opção de configuração.

---

## 4. As 4 Categorias Canônicas

Definidas na metodologia ([OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md)) e gravadas no atributo `category` (structured metadata — consulte com `| category="…"`):

| `category` | Contexto | Exemplos de fontes |
|---|---|---|
| **`security`** | Autenticação e auditoria | SSH, eventos de logon/contas do Windows (Security) |
| **`system`** | Sistema operacional e kernel | kernel (`dmesg`), Event Log System |
| **`application`** | Aplicações, runtimes e bancos | cron, Docker/containerd, logs de containers, Task Scheduler, MySQL, PostgreSQL, SQL Server |
| **`platform`** | Gerenciador de serviços | systemd, Service Control Manager do Windows |

---

## 5. Fontes Coletadas por Tipo de Servidor

### 5.1 Linux (agente — `examples/push/linux`)

Cada fonte do journald é um receiver `journald/<serviço>` que **filtra a severidade na origem** (opção `priority`, repassada ao `journalctl`):

| Receiver | `service.name` | `category` | Severidade mínima |
|---|---|---|---|
| `journald/ssh` (`ssh.service`) | `ssh` | `security` | `info` (todos os eventos de acesso) |
| `journald/kernel` (`_TRANSPORT=kernel`) | `kernel` | `system` | `warning` |
| `journald/cron` (`cron.service`) | `cron` | `application` | `warning` |
| `journald/systemd` (`SYSLOG_IDENTIFIER=systemd`) | `systemd` | `platform` | `warning` |

Conversão comum (operadores compartilhados por âncora YAML): `PRIORITY` → severidade (0–2 `FATAL`, 3 `ERROR`, 4 `WARN`, 5 `INFO2`, 6 `INFO`, 7 `DEBUG`), `_PID` → `process.pid`, `_COMM` → `process.executable.name`, `MESSAGE` → `Body`. Pré-requisito: usuário `otelcol-contrib` no grupo `systemd-journal`.

```bash
sudo journalctl -u otelcol-contrib -n 30 --no-pager | grep "Journalctl command"   # 4 fontes ativas
```

### 5.2 MySQL (`examples/push/linux-mysql`)

Além do journald, `file_log/mysql` lê `/var/log/mysql/error.log` (o padrão `log_error_verbosity=2` do MySQL já grava só `ERROR`, `Warning` e `System`): `[ERROR]` → `ERROR`, `[Warning]` → `WARN`, `[System]`/`[Note]` → `INFO`; o código `MY-nnnnnn` vira `mysql.error.code`, o subsistema `mysql.subsystem` e a thread `thread.id`. `service.name=mysql`, `category=application`. Pré-requisito: usuário `otelcol-contrib` no grupo `adm`.

### 5.3 PostgreSQL (`examples/push/linux-pgsql`)

`file_log/postgresql` lê `/var/log/postgresql/postgresql-*.log` com o prefixo padrão do Debian (`%m [%p] %q%u@%d`), agrupa as linhas de continuação (`DETAIL`, `HINT`, `CONTEXT`, `STATEMENT`) no mesmo registro, normaliza o fuso (`-03` ou `UTC`) e extrai `process.pid`, `user.name` e `db.namespace`. O pipeline mantém só `WARN`+ e as linhas `duration:` (slow queries); `LOG`/`INFO` rotineiros são descartados. `service.name=postgresql`, `category=application`. Pré-requisito: grupo `adm`.

### 5.4 Windows (`examples/push/windows`)

Receivers `windows_event_log` com **filtro XPath na origem** (o XPath do Event Log aceita `!=`, mas não `not()`):

| Receiver | Canal / filtro | `service.name` | `category` |
|---|---|---|---|
| `windows_event_log/security` | Security — IDs 4624, 4625, 4634, 4647, 4648, 4672, 4720, 4725, 4726, 4740, 4767 | `windows-security` | `security` |
| `windows_event_log/system` | System — Critical/Error/Warning, **exceto** o Service Control Manager | `windows-system` | `system` |
| `windows_event_log/services` | System — Service Control Manager, Critical/Error/Warning | `windows-services` | `platform` |
| `windows_event_log/task_scheduler` | TaskScheduler/Operational — Critical/Error/Warning | `windows-task-scheduler` | `application` |

O `Body` é a mensagem do evento; viram atributos `windows.eventlog.event_id`/`provider`/`channel`, `process.pid` e, nos eventos de segurança, `user.name`, `source.address` e `windows.logon.type`. Falha de logon (4625) e bloqueio de conta (4740), registrados como Information pelo Windows, são elevados para `WARN`.

### 5.5 SQL Server (`examples/push/windows-mssql`)

Além das fontes do Windows, `windows_event_log/sqlserver` lê o canal Application filtrando o provider de cada instância listada no XPath (`MSSQLSERVER` para a instância padrão, `MSSQL$<NOME>` para as nomeadas — acrescente uma entrada por instância), Critical/Error/Warning. O receiver não consegue renderizar a mensagem do SQL Server, então o `Body` é montado a partir de `event_data` (`Error: <n> Severity: <s> State: <e> <texto>`) e o número do erro vai para `db.response.status_code`. `service.name=mssql`, `category=application`.

### 5.6 Servidor da própria stack (`otel-agent` em container)

O `otel-agent` (`otel-agent/config.yaml`) usa as mesmas fontes de journald do Linux e acrescenta as do Docker:

| Fonte | `service.name` | `category` | Tratamento da severidade |
|---|---|---|---|
| `journald/docker` (`docker.service`) | `container-engine` | `application` | O `dockerd` grava **tudo** com `PRIORITY=6`, inclusive erros: o nível é extraído do texto (`level=error`) e o pipeline mantém só `WARN`+. |
| `journald/containerd` (`containerd.service`) | `containerd` | `application` | Idem `docker`. |
| `file_log/containers` (`/var/lib/docker/containers/*/*-json.log`) | nome do serviço no compose | `application` | Nível extraído de logfmt (`level=warn`), JSON (`"level":"error"`) ou do formato do Collector; mantém só `WARN`+ e linhas sem nível reconhecido. Containers sem o label `com.docker.compose.service` (fora do compose) são descartados. |

Os containers da stack usam o driver `json-file` com rotação (`x-logging` no `compose.yaml`, `max-size: 10m` / `max-file: 3`) e a opção `labels: com.docker.compose.service`, que grava o nome do serviço em cada linha (vira `service.name` e `container.name`). A posição de leitura é persistida (`file_storage`). Os Collectors da stack registram erros sem *stack trace* (`service.telemetry.logs.disable_stacktrace`), já que cada linha do trace viraria um registro sem nível. Pré-requisito: journal persistente em `/var/log/journal` (padrão no Debian 12+).

```bash
docker logs otel-agent 2>&1 | grep -cE "Journalctl command|Everything is ready"   # 7 = 6 fontes + pronto
```

### 5.7 Servidores coletados por pull

Servidores legados coletados por pull (`examples/pull/`) **não enviam logs** — só métricas dos exporters. Para logs, instale o agente.

---

## 6. Mapeamento do Modelo Anterior (Consultas Legadas)

Referência para reescrever consultas e dashboards criados antes da migração para OpenTelemetry:

| Antes (label Loki) | Agora | Onde fica |
|---|---|---|
| `instance` | `host_name` | label de índice |
| `service_name` | `service_name` | label de índice (de `service.name`) |
| `environment` | `deployment_environment_name` | label de índice |
| `cloud_provider` / `cloud_region` / `cloud_availability_zone` | mesmos nomes | labels de índice |
| `category` | `category` | **structured metadata** (`| category="…"`) |
| `level` (`info`, `warn`, `error`, `critical`) | `severity_text` (`INFO`, `WARN`, `ERROR`, `FATAL`) | structured metadata |
| `container` | `container_name` | label de índice |

Exemplo: `{instance="web-01", category="security"}` vira `{host_name="web-01"} | category="security"`.

---

## 7. Retenção e Armazenamento

A retenção é controlada pela variável `LOKI_RETENTION` do `.env` (padrão `30d`), aplicada pelo *compactor* do Loki (`retention_enabled: true`, `delete_request_store: filesystem` — obrigatório quando há retenção). Para impacto em disco, consulte [SIZING.md](SIZING.md).

---

## 8. Governança e Referências

* Metodologia de observabilidade e correlação entre sinais: [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Topologia, portas e regras de escrita: [ARCHITECTURE.md](ARCHITECTURE.md).
* Métricas e identidade das séries: [METRICS.md](METRICS.md).
* Traces e correlação Log ↔ Trace: [TRACES.md](TRACES.md).
* Instalação de cada agente: `INSTALL.md` de cada template em `examples/push/`.

---
🔙 Voltar: [README Principal](../README.md)
