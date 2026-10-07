# OpenTelemetry Collector — Instalação em Servidor Linux + MySQL (Modo Agent)

Guia para monitorar um servidor Linux que roda **MySQL** (ou MariaDB) com o
agente OpenTelemetry, enviando tudo em OTLP ao `otel-gateway` da stack — com a
[OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).

O servidor de banco é monitorado como **host + banco** no mesmo agente: o
`config.yaml` deste diretório é o template Linux
([examples/push/linux](../linux/INSTALL.md)) acrescido do MySQL.

| Sinal | Origem | Nomes |
|---|---|---|
| Métricas do host | `host_metrics` | `system.*` (idêntico ao template Linux) |
| Logs do host | `journald` | ssh, kernel, cron, systemd |
| Métricas do MySQL | receiver nativo `mysql` | `mysql.*` (~38 séries por instância) |
| Error log do MySQL | `file_log` em `/var/log/mysql/error.log` | `service.name=mysql`, severidade OTel |

Validado com MySQL Community **8.4.11 LTS** (repositório oficial) em Debian 13.
O receiver suporta MySQL 5.7 a 9.x e MariaDB 10.5 a 11.x.

---

## 1. Instalar o Collector e definir a identidade

Siga os passos **1 a 4** do guia Linux ([examples/push/linux/INSTALL.md](../linux/INSTALL.md)):
clonar o repositório, resolver `lgtm-stack`, instalar o `otelcol-contrib` na
versão homologada e definir `OTEL_RESOURCE_ATTRIBUTES` / `LGTM_GATEWAY_ENDPOINT`
em `/etc/otelcol-contrib/otelcol-contrib.conf`.

---

## 2. Usuário de monitoramento no MySQL (privilégios mínimos)

```sql
CREATE USER 'otel_monitor'@'localhost' IDENTIFIED BY '<SENHA_FORTE>'
  WITH MAX_USER_CONNECTIONS 3;
GRANT PROCESS, REPLICATION CLIENT ON *.* TO 'otel_monitor'@'localhost';
GRANT SELECT ON performance_schema.* TO 'otel_monitor'@'localhost';
```

| Privilégio | Para quê |
|---|---|
| `PROCESS` | Estado do InnoDB e das threads |
| `REPLICATION CLIENT` | Status de réplica (quando houver) |
| `SELECT` em `performance_schema.*` | Maioria das métricas do receiver |

> Não conceda `SELECT ON *.*`: o agente não precisa ler dados de negócio.

---

## 3. Credencial do usuário (fora do arquivo de configuração)

A senha **nunca** fica no `config.yaml`. Ela vai para o arquivo de ambiente do
serviço, que passa a ser legível só pelo root e pelo serviço (o pacote cria o
arquivo com modo `644`):

```bash
sudo tee -a /etc/otelcol-contrib/otelcol-contrib.conf << 'EOF'

# Usuário de monitoramento do MySQL (privilégios mínimos)
MYSQL_MONITOR_USER=otel_monitor
MYSQL_MONITOR_PASSWORD=<SENHA_FORTE>
EOF

sudo chown root:otelcol-contrib /etc/otelcol-contrib/otelcol-contrib.conf
sudo chmod 640 /etc/otelcol-contrib/otelcol-contrib.conf
```

---

## 4. Permissões de leitura de logs

```bash
# journald (logs do host)
sudo usermod -aG systemd-journal otelcol-contrib
# /var/log/mysql/error.log (dono mysql:adm, modo 640)
sudo usermod -aG adm otelcol-contrib
```

Confirme onde o MySQL grava o error log e o nível de detalhe (o padrão
`log_error_verbosity=2` grava só `ERROR`, `Warning` e `System` — filtro Lean na
própria origem):

```bash
sudo mysql -Nse "SELECT @@log_error, @@log_error_verbosity"
# esperado: /var/log/mysql/error.log   2
```

> Se o `log_error` apontar para outro arquivo (ou para `stderr`/journald, comum
> no MariaDB do Debian), ajuste `include` do receiver `file_log/mysql`.

---

## 5. Configurar e iniciar

```bash
sudo install -m 0644 ~/lgtm-stack/examples/push/linux-mysql/config.yaml /etc/otelcol-contrib/config.yaml

cd / && sudo -u otelcol-contrib bash -c 'set -a; . /etc/otelcol-contrib/otelcol-contrib.conf; /usr/bin/otelcol-contrib validate --config=/etc/otelcol-contrib/config.yaml' && echo "config OK"

sudo systemctl enable otelcol-contrib
sudo systemctl restart otelcol-contrib
sudo journalctl -u otelcol-contrib -n 30 --no-pager | grep -E "Everything is ready|error|warn"
```

> **Traces e métricas HTTP da aplicação** (opcional): o OBI funciona igual ao
> template Linux — ver seção 6 de [examples/push/linux/INSTALL.md](../linux/INSTALL.md).

---

## 6. O que é coletado do MySQL (Política Lean)

Cada métrica é habilitada ou desabilitada explicitamente no `config.yaml`
(coleta a cada 60 s):

| Grupo | Métricas |
|---|---|
| Saúde | `mysql.server.healthy`, `mysql.uptime` |
| Conexões | `mysql.threads` (connected/running/cached/created), `mysql.max_used_connections`, `mysql.connection.errors` |
| Throughput | `mysql.query.count`, `mysql.query.slow.count`, `mysql.row_operations` |
| Contenção | `mysql.row_locks` (waits, time) |
| InnoDB / memória | `mysql.buffer_pool.usage`, `mysql.buffer_pool.limit`, `mysql.buffer_pool.operations`, `mysql.innodb.redo_log.checkpoint.age` |
| Diagnóstico | `mysql.tmp_resources` (tabelas temporárias em disco) |

> ⚠️ `mysql.table.io.wait.*` e `mysql.index.io.wait.*` vêm **habilitadas por
> padrão** no receiver e geram uma série por tabela/índice. O template as
> desliga explicitamente — não reative em bancos com muitas tabelas.

Identidade: `service.name=mysql` em métricas e logs; o `target_info` traz
`db.system.name`, `db.system.version`, `server.address` e `server.port`.

---

## 7. Verificar o envio de dados

A partir do servidor LGTM (rede interna `lgtm`):

```bash
H="<HOSTNAME_DO_SERVIDOR>"

# Saúde do MySQL (1 = saudável)
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"mysql.server.healthy\", \"host.name\"=\"$H\"}"

# Error log do MySQL
docker run --rm --network lgtm curlimages/curl -sG "http://loki:3100/loki/api/v1/query_range" \
  --data-urlencode "query={host_name=\"$H\", service_name=\"mysql\"}" --data-urlencode 'limit=5'
```

Para comparar com a fonte (devem coincidir, a menos das consultas do próprio
monitoramento):

```bash
sudo mysql -Nse "SELECT VARIABLE_NAME, VARIABLE_VALUE FROM performance_schema.global_status
  WHERE VARIABLE_NAME IN ('Slow_queries','Innodb_row_lock_waits','Questions')"
```

No Grafana: **Explore** → **Mimir** →
`rate({"mysql.query.count", "host.name"="<HOSTNAME>"}[5m])` e **Loki** →
`{service_name="mysql"}` (detalhes: `severity_text`, `mysql.error.code`, `mysql.subsystem`).

---

## Solução de problemas

**`Access denied for user 'otel_monitor'` nos logs do Collector**
```bash
sudo grep MYSQL_MONITOR /etc/otelcol-contrib/otelcol-contrib.conf
mysql -uotel_monitor -p -e "SHOW GRANTS"
```

**Métricas do MySQL ausentes, host OK**
```bash
sudo journalctl -u otelcol-contrib --since "-5m" --no-pager | grep -i mysql
```

**Error log não aparece**
```bash
groups otelcol-contrib            # deve conter adm
sudo systemctl restart otelcol-contrib
```
A leitura começa no fim do arquivo (`start_at: end`) e a posição é guardada
entre reinícios: só entradas novas são enviadas.
