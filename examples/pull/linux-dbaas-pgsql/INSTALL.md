# Coleta Remota — Linux + DBaaS PostgreSQL

> **Objetivo:** Configurar o Alloy Gateway para raspar métricas de Sistema Operacional e do banco PostgreSQL em instâncias gerenciadas (DBaaS) onde não é possível instalar o Alloy Agent.

---

## 1. Endpoints dos Exporters Remotos

Garanta que as rotas de métricas estejam expostas no servidor remoto (frequentemente via proxy reverso na porta `8080` ou portas dedicadas):
* **Sistema Operacional (Node Exporter):** `http://<IP_ADDRESS>:8080/node/metrics` (ou porta `:9100`).
* **PostgreSQL (Postgres Exporter):** `http://<IP_ADDRESS>:8080/postgres/metrics` (ou porta `:9187`).

---

## 2. Configuração no Servidor LGTM (Gateway)

### 2.1 Copiar o Template

```bash
cp examples/pull/linux-dbaas-pgsql/linux-dbaas-pgsql-hosts.alloy alloy-gateway/conf.d/
```

### 2.2 Configurar os Alvos (`targets`)

Edite o arquivo `alloy-gateway/conf.d/linux-dbaas-pgsql-hosts.alloy`:
* Ajuste os blocos `targets` do `pull_linux_node` (SO) e `pull_linux_db` (Postgres) com o IP e nome da instância (`instance`).

### 2.3 Reiniciar o Alloy Gateway

```bash
docker compose restart alloy-gateway
```

---

## 3. Validação Rápida

Abra o dashboard **`Hosts + Database > Linux + PostgreSQL Hosts`** no Grafana para visualizar as métricas de SO e banco.

---
🔙 Voltar: [README Principal](../../../README.md)
