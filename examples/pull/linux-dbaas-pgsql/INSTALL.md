# Coleta Remota — DBaaS PostgreSQL (node_exporter + postgres_exporter)

Para instâncias **PostgreSQL gerenciadas (DBaaS)**, onde não é possível instalar
o agente. O serviço expõe os exporters atrás de um proxy na porta `8080`; o
`otel-agent` da stack faz o scrape, converte para OTLP com a identidade
OpenTelemetry da instância e envia ao `otel-gateway` (que continua só OTLP).

```text
instância DBaaS (rede privada)                    servidor da stack LGTM
:8080/node/metrics      (node_exporter)     <──┐
:8080/postgres/metrics  (postgres_exporter) <──┴─scrape── otel-agent ──OTLP──> otel-gateway
```

| Endpoint | Exporter | Job / `service.name` |
|---|---|---|
| `http://<IP>:8080/node/metrics` | node_exporter (SO da instância) | `node-exporter` |
| `http://<IP>:8080/postgres/metrics` | postgres_exporter (banco) | `postgresql` (convertido; `db.system.name=postgresql`) |

As métricas são convertidas no `otel-agent` para o **mesmo formato do agente**
(`system.*` e `postgresql.*`, OTel Semantic Conventions — processors
`*_node_semconv` e `*_pgsql_semconv` de `otel-agent/pull-semconv.yaml`); o label
`datname` vira **`db.namespace`**. A instância aparece no dashboard
**Linux + PostgreSQL Hosts**, igual a um PostgreSQL com agente
([examples/push/linux-pgsql](../../push/linux-pgsql/INSTALL.md)).

Validado contra instância DBaaS PostgreSQL **16.11** (Magalu Cloud, br-se1).

---

## 1. Conectividade

O servidor da stack precisa alcançar a porta `8080` de cada instância (mesma
VPC, peering ou VPN). Teste a partir do servidor da stack:

```bash
IP="<IP_DA_INSTANCIA>"
curl -s -m 5 -o /dev/null -w "node:     %{http_code}\n" "http://$IP:8080/node/metrics"
curl -s -m 5 -o /dev/null -w "postgres: %{http_code}\n" "http://$IP:8080/postgres/metrics"
```

Os endpoints são HTTP sem autenticação: mantenha a `8080` da instância
acessível **somente** a partir da rede da stack (regras do security group / VPC).

> **Sem rota direta (laboratório):** use túneis SSH por um bastion, como em
> `artifacts/scripts/dns-tunnels.sh` — ex.:
> `ssh -f -N -L 127.0.0.1:18082:<IP>:8080 <bastion>` e alvo
> `host.docker.internal:18082` (o `otel-agent` usa a rede do host).

---

## 2. Configurar o otel-agent

```bash
cd /caminho/para/lgtm-stack
cp examples/pull/linux-dbaas-pgsql/linux-dbaas-pgsql-hosts.yaml otel-agent/pull.d/
```

Edite `otel-agent/pull.d/linux-dbaas-pgsql-hosts.yaml` e declare cada instância
**nos dois jobs** (`node-exporter` e `postgres-exporter`), com o mesmo IP e a
mesma identidade:

```yaml
- targets: ["172.18.2.228:8080"]
  labels:
    host_name: "dbaas-pgsql-01"           # vira host.name
    deployment_environment_name: prd      # vira deployment.environment.name
    cloud_provider: mgc                   # vira cloud.provider
    cloud_region: br-se1                  # vira cloud.region
    cloud_availability_zone: a            # vira cloud.availability_zone
```

Aplique:

```bash
docker compose restart otel-agent
docker logs otel-agent 2>&1 | grep -E "carregando coleta pull|Everything is ready"
```

O arquivo em `otel-agent/pull.d/` contém IPs do ambiente e não é versionado.

---

## 3. O que é coletado (Política Lean)

| Origem | Allowlist | Séries por instância (referência) |
|---|---|---|
| node_exporter → `system.*` | mesma de [examples/pull/linux](../linux/INSTALL.md) + `up` | ~58 numa instância com 4 vCPUs e 2 discos |
| postgres_exporter → `postgresql.*` | `pg_stat_database_*` → `backends`, `commits`, `rollbacks`, `tup_*`, `deadlocks`, `temp.io`, `blks_hit/read`; `pg_database_size_bytes` → `db_size`; `pg_settings_max_connections` → `connection.max`; checkpoints → `bgwriter.checkpoint.count{type}`; `pg_static` → `db.system.version` + `up` | ~30 com 2 bancos de aplicação |

Descartados na origem: os bancos internos `template0`/`template1` (metade das
séries por banco, sem uso operacional), o label `server` (caminho do socket,
igual em toda série), séries sintéticas `scrape_*` e pseudo-dispositivos.
Sem equivalente no receiver (descartados): sessões por estado
(`pg_stat_activity_count`) e tamanho do WAL. Referência: ~30 séries de banco
contra 597 expostas pelo postgres_exporter.

---

## 4. Validação

```bash
H="dbaas-pgsql-01"

# Disponibilidade do scrape
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"up\", \"host.name\"=\"$H\"}"

# Commits por banco
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"postgresql.commits\", \"host.name\"=\"$H\"}"
```

Os contadores devem coincidir com o endpoint de origem (ex.: comparar
`pg_stat_database_xact_commit` do banco em `http://<IP>:8080/postgres/metrics`).

No Grafana: dashboard **Hosts + Database → Linux + PostgreSQL Hosts**,
selecionando a instância.

---

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| `up = 0` | Sem rota até `:8080` (security group, VPC) ou IP errado |
| `up = 1` sem séries `postgresql.*` | Proxy responde, mas o postgres_exporter não conecta ao banco — verificar no painel do DBaaS |
| Métricas do banco com host errado | IP/identidade diferentes entre os jobs `node-exporter` e `postgres-exporter` |

---
🔙 Voltar: [README Principal](../../../README.md)
