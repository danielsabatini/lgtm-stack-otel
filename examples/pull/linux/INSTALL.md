# Coleta Remota — Servidores Linux (Node Exporter)

> **Objetivo:** Configurar o Alloy Gateway central para raspar métricas de Sistema Operacional (CPU, Memória, Disco, Rede) via HTTP direto no `node_exporter` (:9100) de servidores remotos.

---

## 1. Configuração no Servidor Remoto

No servidor Linux que será monitorado, instale e inicie o `node_exporter`:

```bash
# Executar o binário do node_exporter expondo a porta :9100
sudo systemctl enable --now node_exporter
```

---

## 2. Configuração no Servidor LGTM (Gateway)

### 2.1 Copiar o Template

No servidor central da LGTM Stack:

```bash
cp examples/pull/linux/linux-hosts.alloy alloy-gateway/conf.d/
```

### 2.2 Configurar os Alvos (`targets`)

Edite o arquivo `alloy-gateway/conf.d/linux-hosts.alloy` adicionando os servidores:

```alloy
prometheus.scrape "pull_linux_host" {
  targets = [
    {
      "__address__"             = "192.168.1.10:9100",
      "instance"                = "srv-app-01",
      "environment"             = "prd",
      "cloud_provider"          = "mgc",
      "cloud_region"            = "br-se1",
      "cloud_availability_zone" = "a",
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

Abra o dashboard **`Hosts > Linux Hosts`** no Grafana para visualizar o host monitorado.

---
🔙 Voltar: [README Principal](../../../README.md)
