# Coleta Remota — DBaaS MySQL (node_exporter + mysqld_exporter)

Para instâncias **MySQL gerenciadas (DBaaS)**, onde não é possível instalar o
agente. O serviço expõe os exporters atrás de um proxy na porta `8080`; o
`otel-agent` da stack faz o scrape, converte para OTLP com a identidade
OpenTelemetry da instância e envia ao `otel-gateway` (que continua só OTLP).

```text
instância DBaaS (rede privada)                 servidor da stack LGTM
:8080/node/metrics   (node_exporter)   <──┐
:8080/mysql/metrics  (mysqld_exporter) <──┴─scrape── otel-agent ──OTLP──> otel-gateway
```

| Endpoint | Exporter | Job / `service.name` |
|---|---|---|
| `http://<IP>:8080/node/metrics` | node_exporter (SO da instância) | `node-exporter` |
| `http://<IP>:8080/mysql/metrics` | mysqld_exporter (banco) | `mysql` (convertido; `db.system.name=mysql`) |

As métricas são convertidas no `otel-agent` para o **mesmo formato do agente**
(`system.*` e `mysql.*`, OTel Semantic Conventions — processors `*_node_semconv`
e `*_mysql_semconv` de `otel-agent/pull-semconv.yaml`): a instância aparece no
dashboard **Linux + MySQL Hosts**, igual a um MySQL com agente
([examples/push/linux-mysql](../../push/linux-mysql/INSTALL.md)).

Validado contra instância DBaaS MySQL **8.4.6** (Magalu Cloud, br-se1).

---

## 1. Conectividade

O servidor da stack precisa alcançar a porta `8080` de cada instância (mesma
VPC, peering ou VPN). Teste a partir do servidor da stack:

```bash
IP="<IP_DA_INSTANCIA>"
curl -s -m 5 -o /dev/null -w "node:  %{http_code}\n" "http://$IP:8080/node/metrics"
curl -s -m 5 -o /dev/null -w "mysql: %{http_code}\n" "http://$IP:8080/mysql/metrics"
```

Os endpoints são HTTP sem autenticação: mantenha a `8080` da instância
acessível **somente** a partir da rede da stack (regras do security group / VPC).

> **Sem rota direta (laboratório):** use túneis SSH por um bastion, como em
> `artifacts/scripts/dns-tunnels.sh` — ex.:
> `ssh -f -N -L 127.0.0.1:18081:<IP>:8080 <bastion>` e alvo
> `host.docker.internal:18081` (o `otel-agent` usa a rede do host).

---

## 2. Configurar o otel-agent

```bash
cd /caminho/para/lgtm-stack
cp examples/pull/linux-dbaas-mysql/linux-dbaas-mysql-hosts.yaml otel-agent/pull.d/
```

Edite `otel-agent/pull.d/linux-dbaas-mysql-hosts.yaml` e declare cada
instância **nos dois jobs** (`node-exporter` e `mysqld-exporter`), com o mesmo
IP e a mesma identidade:

```yaml
- targets: ["172.18.1.234:8080"]
  labels:
    host_name: "dbaas-mysql-01"           # vira host.name
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
| mysqld_exporter → `mysql.*` | `mysql_up` → `server.healthy`, `uptime`, `queries` → `query.count`, `slow_queries`, `threads_*` → `threads{kind}`, `max_used_connections`, erros de conexão (+ `aborted_*`), `innodb_row_lock_*` → `row_locks{kind}`, `innodb_system_rows_*` → `row_operations`, `created_tmp_*` → `tmp_resources`, buffer pool (uso clean/dirty, limite, operações), idade do checkpoint do redo; versão em `db.system.version` | ~33 |

O `mysqld_exporter` publica os contadores do `SHOW GLOBAL STATUS` como *untyped*:
a conversão os grava como Sum cumulativo, como o receiver. O exporter do MySQL
8.4 só expõe `Innodb_system_rows_*`, usados para `mysql.row_operations`.

Contra ~1.500 (node) + ~3.000 (mysqld) séries expostas. Séries sintéticas
`scrape_*` e pseudo-dispositivos/filesystems são descartados.

---

## 4. Validação

```bash
H="dbaas-mysql-01"

# Disponibilidade: up (scrape) e mysql.server.healthy (exporter conectado ao banco)
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={__name__=~\"up|mysql.server.healthy\", \"host.name\"=\"$H\"}"

# Séries por job
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=count by (job) ({\"host.name\"=\"$H\"})"
```

No Grafana: dashboard **Hosts + Database → Linux + MySQL Hosts**, selecionando a
instância.

---

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| `up = 0` | Sem rota até `:8080` (security group, VPC) ou IP errado |
| `up = 1` e `mysql.server.healthy = 0` | Proxy responde, mas o mysqld_exporter não conecta ao banco — verificar no painel do DBaaS |
| Métricas do banco com host errado | IP/identidade diferentes entre os jobs `node-exporter` e `mysqld-exporter` |

---
🔙 Voltar: [README Principal](../../../README.md)
