# Coleta Remota — Windows Server + Microsoft SQL Server (MSSQL)

> **Objetivo:** Configurar o Alloy Gateway da stack central para raspar métricas de Sistema Operacional Windows e do banco SQL Server (PLE, Buffer Cache Hit, Locks, Page I/O) via HTTP direto no `windows_exporter` (:9182).

---

## 1. Configuração no Servidor Windows Remoto

1. Instale o [windows_exporter](https://github.com/prometheus-community/windows_exporter).
2. Configure o arquivo `config.yml` habilitando os coletores de SO e o coletor de SQL Server (`mssql`):
   ```yaml
   collectors:
     enabled: cpu,logical_disk,memory,net,os,system,mssql,pagefile
   ```
3. Execute o serviço expondo a porta `:9182`.

---

## 2. Configuração no Servidor LGTM (Gateway)

### 2.1 Copiar o Template

No servidor central da LGTM Stack:

```bash
cp examples/pull/windows-mssql/windows-mssql-hosts.alloy alloy-gateway/conf.d/
```

### 2.2 Configurar os Alvos (`targets`)

Edite o arquivo `alloy-gateway/conf.d/windows-mssql-hosts.alloy` ajustando os blocos de SO e MSSQL com o IP e nome da máquina (`instance`).

### 2.3 Reiniciar o Alloy Gateway

```bash
docker compose restart alloy-gateway
```

---

## 3. Validação Rápida

Abra o dashboard **`Hosts + Database > Windows + MSSQL Hosts`** no Grafana para visualizar as métricas de Sistema Operacional e do banco SQL Server em tempo real.

---
🔙 Voltar: [README Principal](../../../README.md)
