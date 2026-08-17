# Coleta Remota — Servidores Windows (windows_exporter)

> **Objetivo:** Configurar o Alloy Gateway da stack central para raspar métricas de Sistema Operacional Windows (CPU, Memória, Logical Disk, Network, Pagefile) via HTTP direto no `windows_exporter` (:9182).

---

## 1. Configuração no Servidor Windows Remoto

1. Instale e inicie o [windows_exporter](https://github.com/prometheus-community/windows_exporter).
2. Configure o arquivo `config.yml` ativando apenas os coletores necessários:
   ```yaml
   collectors:
     enabled: cpu,logical_disk,memory,net,os,system,pagefile
   ```
3. Execute o serviço expondo a porta `:9182`.

---

## 2. Configuração no Servidor LGTM (Gateway)

### 2.1 Copiar o Template

No servidor central da LGTM Stack:

```bash
cp examples/pull/windows/windows-hosts.alloy alloy-gateway/conf.d/
```

### 2.2 Configurar os Alvos (`targets`)

Edite o arquivo `alloy-gateway/conf.d/windows-hosts.alloy` adicionando seus servidores:

```alloy
prometheus.scrape "pull_windows_host" {
  targets = [
    {
      "__address__"             = "[IP_ADDRESS]:9182",
      "instance"                = "[INSTANCE_NAME]",
      "environment"             = "prd",
      "cloud_provider"          = "mgc",
      "cloud_region"            = "[REGION]",
      "cloud_availability_zone" = "[ZONE]",
    },
  ]
  ...
}
```

### 2.3 Reiniciar o Alloy Gateway

```bash
docker compose restart alloy-gateway
```

---

## 3. Validação Rápida

Abra o dashboard **`Hosts > Windows Hosts`** no Grafana (`http://<IP_LGTM>:3000`) para visualizar o host monitorado.

---
🔙 Voltar: [README Principal](../../../README.md)
