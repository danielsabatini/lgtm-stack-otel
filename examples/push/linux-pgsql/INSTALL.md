# OpenTelemetry Collector — Instalação em Servidor Linux + PostgreSQL (Modo Agent)

Guia para monitorar um servidor Linux que roda **PostgreSQL** com o agente
OpenTelemetry, enviando tudo em OTLP ao `otel-gateway` da stack — com a
[OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).

O servidor de banco é monitorado como **host + banco** no mesmo agente: o
`config.yaml` deste diretório é o template Linux
([examples/push/linux](../linux/INSTALL.md)) acrescido do PostgreSQL.

| Sinal | Origem | Nomes |
|---|---|---|
| Métricas do host | `host_metrics` | `system.*` (idêntico ao template Linux) |
| Logs do host | `journald` | ssh, kernel, cron, systemd |
| Métricas do PostgreSQL | receiver nativo `postgresql` | `postgresql.*` por banco (`db.namespace`), ~14 séries por banco |
| Log do PostgreSQL | `file_log` em `/var/log/postgresql/postgresql-*.log` | `service.name=postgresql`, severidade OTel, `db.namespace`, `user.name` |

Validado com PostgreSQL **18.6** (repositório oficial PGDG) em Debian 13.

---

## 1. Instalar o Collector e definir a identidade

Siga os passos **1 a 4** do guia Linux ([examples/push/linux/INSTALL.md](../linux/INSTALL.md)):
clonar o repositório, resolver `lgtm-stack`, instalar o `otelcol-contrib` na
versão homologada e definir `OTEL_RESOURCE_ATTRIBUTES` / `LGTM_GATEWAY_ENDPOINT`
em `/etc/otelcol-contrib/otelcol-contrib.conf`.

---

## 2. Usuário de monitoramento no PostgreSQL (privilégios mínimos)

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE otel_monitor LOGIN PASSWORD '<SENHA_FORTE>' CONNECTION LIMIT 3;
GRANT pg_monitor TO otel_monitor;
SQL
```

A role padrão `pg_monitor` dá leitura às views de estatística (`pg_stat_*`) —
o agente não lê dados de negócio. Confirme que o `pg_hba.conf` aceita senha
para `localhost` (padrão do Debian: `scram-sha-256` em `host all all 127.0.0.1/32`).

---

## 3. Credencial e feature gate (arquivo de ambiente do serviço)

```bash
sudo tee -a /etc/otelcol-contrib/otelcol-contrib.conf << 'EOF'

# Usuário de monitoramento do PostgreSQL (role pg_monitor)
PG_MONITOR_USER=otel_monitor
PG_MONITOR_PASSWORD=<SENHA_FORTE>
EOF

# Feature gate OBRIGATÓRIO (ver abaixo)
sudo sed -i 's#^OTELCOL_OPTIONS=.*#OTELCOL_OPTIONS="--config=/etc/otelcol-contrib/config.yaml --feature-gates=+receiver.postgresql.useOTelSemconv"#' \
  /etc/otelcol-contrib/otelcol-contrib.conf

# Arquivo legível só pelo root e pelo serviço (o pacote cria com 644)
sudo chown root:otelcol-contrib /etc/otelcol-contrib/otelcol-contrib.conf
sudo chmod 640 /etc/otelcol-contrib/otelcol-contrib.conf
```

> **Por que o feature gate `receiver.postgresql.useOTelSemconv`?** Sem ele, o
> receiver cria um resource por banco, tabela e índice e guarda o nome do banco
> só no resource — no Mimir, as séries de bancos diferentes ficariam com labels
> idênticas e se misturariam. Com ele, há **um resource por servidor** e o
> banco vira o atributo `db.namespace` da OTel Semantic Conventions em cada
> série. O gate é **Alpha** no Collector `0.162.0`: revalide-o a cada upgrade
> (`otelcol-contrib featuregate | grep postgresql`).

---

## 4. Permissões de leitura de logs

```bash
sudo usermod -aG systemd-journal otelcol-contrib   # journald
sudo usermod -aG adm otelcol-contrib               # /var/log/postgresql (postgres:adm, 640)
```

O receiver espera o prefixo padrão do Debian (`log_line_prefix = '%m [%p] %q%u@%d '`):

```bash
sudo -u postgres psql -Atc "SHOW log_line_prefix; SHOW log_min_messages; SHOW log_min_duration_statement"
# esperado: %m [%p] %q%u@%d    warning    -1
```

> **Slow queries:** para registrá-las, defina `log_min_duration_statement`
> (ex.: `ALTER SYSTEM SET log_min_duration_statement = '1s'; SELECT pg_reload_conf();`).
> As linhas `duration:` são preservadas pelo filtro do agente.

---

## 5. Configurar e iniciar

```bash
sudo install -m 0644 ~/lgtm-stack/examples/push/linux-pgsql/config.yaml /etc/otelcol-contrib/config.yaml

cd / && sudo -u otelcol-contrib bash -c 'set -a; . /etc/otelcol-contrib/otelcol-contrib.conf; /usr/bin/otelcol-contrib validate $OTELCOL_OPTIONS' && echo "config OK"

sudo systemctl enable otelcol-contrib
sudo systemctl restart otelcol-contrib
sudo journalctl -u otelcol-contrib -n 30 --no-pager | grep -E "Everything is ready|error|warn"
```

> **Traces e métricas HTTP da aplicação** (opcional): o OBI funciona igual ao
> template Linux — ver seção 6 de [examples/push/linux/INSTALL.md](../linux/INSTALL.md).

---

## 6. O que é coletado do PostgreSQL (Política Lean)

Só métricas no **nível de banco** (`db.namespace`), cada uma habilitada
explicitamente (coleta a cada 60 s):

| Grupo | Métricas |
|---|---|
| Conexões | `postgresql.backends`, `postgresql.connection.max` (saturação = backends / max) |
| Transações | `postgresql.commits`, `postgresql.rollbacks` |
| Throughput | `postgresql.tup_fetched`, `tup_returned`, `tup_inserted`, `tup_updated`, `tup_deleted` |
| Contenção / diagnóstico | `postgresql.deadlocks`, `postgresql.temp.io` |
| Cache | `postgresql.blks_hit`, `postgresql.blks_read` (hit ratio) |
| Capacidade | `postgresql.db_size`, `postgresql.bgwriter.checkpoint.count` |

> ⚠️ O receiver habilita por padrão métricas **por tabela e por índice**
> (`postgresql.blocks_read`, `operations`, `rows`, `index.*`, `table.*`), cuja
> cardinalidade cresce com o schema. O template as desliga explicitamente.

Log: `WARNING`, `ERROR`, `FATAL`, `PANIC` e as linhas `duration:` de slow
query; as linhas de continuação (`DETAIL`, `HINT`, `CONTEXT`, `STATEMENT`) são
agrupadas no mesmo registro. `LOG`/`INFO` rotineiros (startup, checkpoints)
são descartados.

---

## 7. Verificar o envio de dados

A partir do servidor LGTM (rede interna `lgtm`):

```bash
H="<HOSTNAME_DO_SERVIDOR>"

# Commits por banco
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"postgresql.commits\", \"host.name\"=\"$H\"}"

# Log do PostgreSQL
docker run --rm --network lgtm curlimages/curl -sG "http://loki:3100/loki/api/v1/query_range" \
  --data-urlencode "query={host_name=\"$H\", service_name=\"postgresql\"}" --data-urlencode 'limit=5'
```

Compare com a fonte (devem coincidir, a menos das consultas feitas entre as leituras):

```bash
sudo -u postgres psql -Atc "SELECT datname, xact_commit, xact_rollback, deadlocks, tup_inserted FROM pg_stat_database WHERE datname NOT LIKE 'template%'"
```

No Grafana: **Explore** → **Mimir** →
`sum by ("db.namespace") (rate({"postgresql.commits", "host.name"="<HOSTNAME>"}[5m]))`
e **Loki** → `{service_name="postgresql"} | severity_text="ERROR"`.

---

## Solução de problemas

**`password authentication failed for user "otel_monitor"` (no log do Collector e do PostgreSQL)**
```bash
sudo grep PG_MONITOR /etc/otelcol-contrib/otelcol-contrib.conf
PGPASSWORD='<SENHA>' psql -h localhost -U otel_monitor -d postgres -c "select 1"
```

**Séries de bancos diferentes misturadas / sem `db.namespace`**
O feature gate não está ativo:
```bash
sudo grep ^OTELCOL_OPTIONS /etc/otelcol-contrib/otelcol-contrib.conf   # deve conter useOTelSemconv
systemctl show otelcol-contrib -p ExecMainPID --value | xargs -I{} cat /proc/{}/cmdline | tr '\0' ' '
```

**Log não aparece**
```bash
groups otelcol-contrib            # deve conter adm
ls -l /var/log/postgresql/        # o arquivo deve ser postgres:adm
```
Se o timestamp do log não for reconhecido (prefixo diferente do padrão
Debian), ajuste o `regex_parser` do receiver `file_log/postgresql`.
