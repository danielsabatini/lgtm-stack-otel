# Coleta Remota — Cluster DNS Interno (CoreDNS + etcd + Linux)

> **Objetivo:** Configurar o Alloy Gateway da stack central para realizar o scraping remoto (Modo Pull) nos 3 servidores de DNS interno (*CoreDNS :9153, etcd :2379 e Node Exporter :9100*).

---

## 1. Arquivos Disponíveis nesta Pasta

* **`linux-dns-hosts.alloy`:** Scrape do Sistema Operacional (CPU, Memória, Disco, Rede na porta `:9100`).
* **`coredns-hosts.alloy`:** Scrape do CoreDNS (Status, Latência p99, Upstream Health na porta `:9153`).
* **`etcd-hosts.alloy`:** Scrape do etcd (Consenso Raft, Quorum, Storage, Fsync na porta `:2379`).

---

## 2. Passo a Passo de Ativação no Servidor LGTM

### 2.1 Copiar os Pipelines para o Gateway

No servidor central da LGTM Stack:

```bash
# Copiar os 3 arquivos para a pasta conf.d do Gateway
cp examples/pull/dns/*.alloy alloy-gateway/conf.d/
```

### 2.2 Ajustar os IPs dos Servidores (se necessário)

Edite os arquivos em `alloy-gateway/conf.d/` e ajuste os IPs e zonas no bloco `targets` (caso seus IPs sejam diferentes do exemplo):

```alloy
targets = [
  { "__address__" = "172.18.1.2:9153",  "instance" = "dns-ne1-1", "cloud_availability_zone" = "a" },
  { "__address__" = "172.18.17.2:9153", "instance" = "dns-ne1-2", "cloud_availability_zone" = "b" },
  { "__address__" = "172.18.33.2:9153", "instance" = "dns-ne1-3", "cloud_availability_zone" = "c" },
]
```

### 2.3 Reiniciar o Alloy Gateway

```bash
# Reiniciar o serviço para carregar as novas coletas
docker compose restart alloy-gateway
```

---

## 3. Validação Rápida

```bash
# Conferir se o Gateway subiu sem erros
docker compose logs -f alloy-gateway
```

Abra o dashboard **`DNS > MGC Internal DNS`** no Grafana (`http://<IP_LGTM>:3000`) para visualizar a saúde das 3 camadas em tempo real.

---
🔙 Voltar: [README Principal](../../../README.md)
