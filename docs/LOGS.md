# Logs (Loki e OpenTelemetry)

> **Referência Técnica:** Este documento estabelece a política de categorização, labels, pipelines de coleta e retenção de logs no Grafana Loki.

---

## 1. Introdução

A agregação de logs na LGTM Stack é desenhada para oferecer busca em tempo real com baixo consumo de armazenamento. Em vez de indexar o texto completo de cada linha (o que geraria índices gigantescos e lentidão), o Grafana Loki indexa apenas os **metadados (labels)** e compacta o conteúdo das mensagens em blocos (*chunks*).

Para evitar que o Loki se torne um repositório confuso de mensagens desordenadas, todos os logs coletados são enriquecidos com uma categoria funcional padronizada.

---

## 2. Objetivo

1. **Estruturar os Logs por Categoria:** Garantir que todos os logs pertençam a uma das 4 categorias canônicas de observabilidade.
2. **Definir Padrão de Labels:** Padronizar as tags de identificação de instâncias, serviços e severidade.
3. **Controlar o Descarte de Ruído:** Filtrar na origem logs rotineiros desnecessários para economizar até 80% de armazenamento.

---

## 3. Endpoints e Roteamento de Ingestão

Toda a ingestão de logs é centralizada no **OTel Gateway**:
* **Portas 4317 / 4318:** Única entrada de logs — OTLP vindo dos agents e das aplicações. A API de push do Loki (antiga porta 9998) foi removida.

### 3.1 Logs OTLP (Semântica OpenTelemetry)

Logs OTLP são gravados no endpoint OTLP nativo do Loki (`otelcol.exporter.otlphttp "loki"` → `http://loki:3100/otlp/v1/logs`), seguindo o [OTel Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/):

| Campo OTel | Onde fica no Loki | Exemplo de consulta |
|---|---|---|
| Resource attributes de identidade (`service.name`, `service.namespace`, `service.instance.id`, `deployment.environment.name`, `host.name`, `cloud.provider`, `cloud.region`, `cloud.availability_zone`) | **Index labels** (o Loki troca `.` por `_`) | `{service_name="checkout", host_name="app-host-01"}` |
| `Body` | Linha do log (texto puro) | `|= "payment declined"` |
| `SeverityText` / `SeverityNumber` | Structured metadata `severity_text` / `severity_number` | `| severity_text="ERROR"` |
| `TraceId` / `SpanId` | Structured metadata `trace_id` / `span_id` | `| trace_id="04d102d4..."` |
| Demais atributos (resource e log record) | Structured metadata | `| service_version="1.4.2"` |

A lista de index labels é definida em `limits_config.otlp_config` (`loki/loki.yaml`) somada aos defaults do Loki. Não promova atributos de alta cardinalidade (IDs de requisição, usuário) a index label.

Os links do Grafana usam esses campos: **Log → Trace** pelo derived field `TraceID` (tipo *label*, lê `trace_id` do structured metadata) e **Trace → Logs** pela query `{service_name="<service.name do span>"} | trace_id="<trace>"` (`grafana/provisioning/datasources/datasources.yaml`).

---

## 4. As 4 Categorias Padronizadas de Logs

Conforme definido na metodologia de observabilidade ([OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md)), todos os logs recebem a label `category` para facilitar a filtragem nos dashboards:

| Categoria (`category`) | Contexto Operacional | O que Coleta |
|---|---|---|
| **`security`** | Autenticação e Auditoria | Acessos SSH, logins em painéis, bloqueios de firewall/ACL e comandos `sudo`. |
| **`system`** | Sistema Operacional e Kernel | Mensagens de boot, eventos do kernel (`dmesg`), intervenções do OOM Killer e erros de disco. |
| **`application`** | Aplicações e Runtimes | Logs de contêineres Docker/containerd, tarefas agendadas (`cron`), exceções e queries lentas. |
| **`platform`** | Gerenciador de Serviços | Inicialização, paradas inesperadas e ciclo de vida de daemons no `systemd` e Windows SCM. |

---

## 5. Pipelines de Coleta no Host Linux (Agent OpenTelemetry)

No agente OpenTelemetry (`examples/push/linux/config.yaml`), cada fonte do journald é um receiver `journald/<serviço>` que **filtra a severidade na origem** (opção `priority`, repassada ao `journalctl`) e converte a entrada do journal no OTel Logs Data Model:

| Receiver | `service.name` | `category` | Severidade mínima coletada |
|---|---|---|---|
| `journald/ssh` (`ssh.service`) | `ssh` | `security` | `info` (todos os eventos de acesso) |
| `journald/kernel` (`_TRANSPORT=kernel`) | `kernel` | `system` | `warning` |
| `journald/cron` (`cron.service`) | `cron` | `application` | `warning` |
| `journald/systemd` (`SYSLOG_IDENTIFIER=systemd`) | `systemd` | `platform` | `warning` |

Conversão comum a todos (operadores YAML compartilhados por âncora): `PRIORITY` → `SeverityNumber`/`SeverityText` (0–2 `FATAL`, 3 `ERROR`, 4 `WARN`, 5 `INFO2`, 6 `INFO`, 7 `DEBUG`), `_PID` → `process.pid`, `_COMM` → `process.executable.name`, `MESSAGE` → Body. No Loki: `service_name` e `host_name` são labels de índice; `category`, `severity_text`, `process_pid` e `process_executable_name` ficam como structured metadata. Pré-requisito: o usuário `otelcol-contrib` no grupo `systemd-journal`.

Verificação:

```bash
sudo journalctl -u otelcol-contrib -n 30 --no-pager | grep "Journalctl command"   # 4 fontes ativas
```

**Servidores MySQL** (`examples/push/linux-mysql`): além do journald, o receiver `file_log/mysql` lê `/var/log/mysql/error.log` (o MySQL grava só `ERROR`, `Warning` e `System` com o padrão `log_error_verbosity=2`). `[Warning]` → `WARN`, `[ERROR]` → `ERROR`, `[System]`/`[Note]` → `INFO`; o código `MY-nnnnnn` vira `mysql.error.code`, o subsistema `mysql.subsystem` e a thread `thread.id`, com `service.name=mysql`. Pré-requisito: usuário `otelcol-contrib` no grupo `adm`.

**Servidores PostgreSQL** (`examples/push/linux-pgsql`): o receiver `file_log/postgresql` lê `/var/log/postgresql/postgresql-*.log` com o prefixo padrão do Debian (`%m [%p] %q%u@%d`), agrupa as linhas de continuação (`DETAIL`, `HINT`, `CONTEXT`, `STATEMENT`) no mesmo registro, converte `WARNING`/`ERROR`/`FATAL`/`PANIC` para a severidade OTel e extrai `process.pid`, `user.name` e `db.namespace`. O pipeline mantém só `WARN`+ e as linhas `duration:` (slow query); `LOG`/`INFO` rotineiros são descartados. Pré-requisito: usuário `otelcol-contrib` no grupo `adm`.

### 5.1 Servidor da própria stack (`otel-agent` em container)

O `otel-agent` (`otel-agent/config.yaml`, serviço no `compose.yaml`) usa as mesmas fontes de journald acima e acrescenta as do Docker:

| Fonte | `service.name` | `category` | Como a severidade é tratada |
|---|---|---|---|
| `journald/docker` (`docker.service`) | `container-engine` | `application` | O `dockerd` grava **tudo** no journal com `PRIORITY=6`, inclusive erros: o nível real é extraído do texto (`level=error`) e o pipeline `logs/engine` mantém só `WARN`+. |
| `journald/containerd` (`containerd.service`) | `containerd` | `application` | Idem `docker`. |
| `file_log/containers` (`/var/lib/docker/containers/*/*-json.log`) | nome do serviço no compose | `application` | Nível extraído de logfmt (`level=warn`), JSON (`"level":"error"`) ou do formato do próprio Collector; mantém só `WARN`+ e linhas sem nível reconhecido. |

Os logs de container usam o driver `json-file` declarado para todos os serviços da stack (`x-logging` no `compose.yaml`, com rotação `max-size: 10m` / `max-file: 3`). A opção `labels: com.docker.compose.service` grava o nome do serviço em cada linha, que vira `service.name` e `container.name`; o `container.id` vem do caminho do arquivo. A posição de leitura é persistida (`file_storage`), sem reler nem perder linhas após reinício.

Pré-requisito no host: journal persistente em `/var/log/journal` (padrão no Debian 12+). Sem ele o `journalctl` do container encerra e o receiver tenta novamente a cada segundo (`journalctl command exited` nos logs do `otel-agent`).

Verificação:

```bash
docker logs otel-agent 2>&1 | grep -cE "Journalctl command|Everything is ready"   # 7 = 6 fontes + pronto
```

---

## 6. Coleta no Windows (Windows Event Log)

No Windows, o agente lê diretamente da API nativa do **Windows Event Log**:

| Categoria | Canal do Event Log | O que Coleta |
|---|---|---|
| `security` | `Security` | Eventos de logon (4624/4625), privilégios e auditoria de contas. |
| `system` | `System` | Erros de hardware, drivers e falhas do sistema operacional. |
| `application` | `TaskScheduler/Operational` | Falhas no Agendador de Tarefas do Windows. |
| `platform` | `System` (Provider: SCM) | Falhas de inicialização e paradas de serviços do Windows. |
| `database` | `Application` (Provider: MSSQL) | Erros transacionais e alertas do SQL Server (Severity ≥ 17). |

---

## 7. Esquema Global de Labels

Os streams coletados pelos agents legados em Alloy carregam os labels de identidade abaixo; no agente OpenTelemetry a identidade segue a seção 3.1. Logs OTLP de aplicações seguem o mapeamento semântico da seção 3.1.

| Label | Descrição | Exemplo |
|---|---|---|
| `category` | Categoria funcional do log | `security`, `system`, `application`, `platform` |
| `service_name` | Nome do serviço de origem | `ssh`, `kernel`, `coredns`, `container-engine` |
| `level` | Nível de severidade da mensagem | `info`, `warning`, `error` |
| `instance` | Identificador único do host | `dns-ne1-1`, `db-prod-01` |
| `environment` | Ambiente de implantação | `prd`, `stg`, `dev` |
| `cloud_provider` | Provedor de nuvem | `mgc`, `aws`, `local` |
| `cloud_region` | Região geográfica | `br-se1`, `br-ne1` |

---

## 8. Retenção e Armazenamento

A retenção é controlada pela variável `LOKI_RETENTION` no arquivo `.env` (padrão: `30d`). A limpeza de chunks antigos ocorre automaticamente pelo componente *compactor* do Loki.

Para cálculos de impacto em disco e dimensionamento, consulte [SIZING.md](SIZING.md).

---

## 9. Governança e Referências

* Para a metodologia completa de observabilidade e correlação com métricas/traces, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para a topologia de rede e isolamento do Gateway, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](../README.md)
