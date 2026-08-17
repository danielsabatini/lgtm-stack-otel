# Coleta Remota — Linux + DBaaS MySQL

> **Objetivo:** Configurar o Alloy Gateway para raspar métricas de Sistema Operacional e do motor MySQL / MariaDB (InnoDB, conexões, queries) em instâncias gerenciadas (DBaaS).

---

## 1. Endpoints dos Exporters Remotos

Garanta que as rotas de métricas estejam expostas no servidor remoto (frequentemente via proxy reverso na porta `8080` ou portas dedicadas):
* **Sistema Operacional (Node Exporter):** `http://<IP_ADDRESS>:8080/node/metrics` (ou porta `:9100`).
* **MySQL (MySQL Exporter):** `http://<IP_ADDRESS>:8080/mysql/metrics` (ou porta `:9104`).

---

## 2. Configuração no Servidor LGTM (Gateway)

### 2.1 Copiar o Template

```bash
cp examples/pull/linux-dbaas-mysql/linux-dbaas-mysql-hosts.alloy alloy-gateway/conf.d/
```

### 2.2 Configurar os Alvos (`targets`)

Edite o arquivo `alloy-gateway/conf.d/linux-dbaas-mysql-hosts.alloy`:
* Ajuste os blocos `targets` do `pull_linux_node` (SO) e `pull_linux_db` (MySQL) com o IP e nome da instância (`instance`).

### 2.3 Reiniciar o Alloy Gateway

```bash
docker compose restart alloy-gateway
```

---

## 3. Validação Rápida

Abra o dashboard **`Hosts + Database > Linux + MySQL Hosts`** no Grafana para visualizar as métricas de SO e banco.

---
🔙 Voltar: [README Principal](../../../README.md)
