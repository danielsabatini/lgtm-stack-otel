# Coleta Remota — Servidores Linux Legados (node_exporter)

Para servidores onde **não é possível instalar o agente OpenTelemetry** e só há
o `node_exporter`. O `otel-agent` da stack faz o scrape do `node_exporter`
(`:9100`), converte as métricas para o **mesmo formato do agente** (`system.*`,
OTel Semantic Conventions) com a identidade OpenTelemetry do servidor e envia ao
`otel-gateway` — o Gateway continua recebendo só OTLP, sem conversão.

```text
servidor legado            servidor da stack LGTM
node_exporter :9100  <──scrape──  otel-agent ──OTLP──> otel-gateway ──> Mimir
```

| Aspecto | Pull legado (este guia) | Agente OpenTelemetry ([push/linux](../../push/linux/INSTALL.md)) |
|---|---|---|
| Métricas | `system.*` (convertidas de `node_*` no `otel-agent`) | `system.*` (OTel Semantic Conventions) |
| Dashboard | **Linux Hosts** (o mesmo do agente) | **Linux Hosts** |
| Logs (journald) | ❌ não disponível | ✅ |
| Traces / métricas HTTP (OBI) | ❌ | ✅ |
| Identidade | declarada por alvo neste template | detectada no próprio host |

> **Prefira o agente** sempre que possível. Use o pull apenas como transição
> para servidores legados.

---

## 1. No servidor remoto (legado)

### 1.1 Instalar o node_exporter

```bash
# Debian / Ubuntu
sudo apt-get install -y prometheus-node-exporter
sudo systemctl enable --now prometheus-node-exporter

# Conferir
curl -s localhost:9100/metrics | grep -c '^node_'
```

### 1.2 Restringir o acesso à porta 9100 (obrigatório)

O `node_exporter` expõe `:9100` em HTTP **sem autenticação**. Libere a porta
**somente para o IP do servidor da stack** (o `otel-agent` usa a rede do host):

```bash
STACK_IP="<IP_DO_SERVIDOR_LGTM>"

# ufw
sudo ufw allow from "$STACK_IP" to any port 9100 proto tcp
sudo ufw deny 9100/tcp

# ou iptables
sudo iptables -A INPUT -p tcp --dport 9100 -s "$STACK_IP" -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 9100 -j DROP
```

> O `otel-agent` não abre portas: ele só **inicia** conexões (stack → `:9100`
> do servidor legado). O que precisa de proteção é o `node_exporter`.

---

## 2. No servidor da stack LGTM

### 2.1 Copiar o template para o otel-agent

```bash
cd /caminho/para/lgtm-stack
cp examples/pull/linux/linux-hosts.yaml otel-agent/pull.d/linux-hosts.yaml
```

Todo arquivo `*.yaml` em `otel-agent/pull.d/` é carregado pelo `otel-agent`
junto com o `config.yaml` (ver `otel-agent/entrypoint.sh`). Esses arquivos
contêm IPs do ambiente e **não são versionados** (`.gitignore`).

### 2.2 Declarar os alvos e a identidade de cada servidor

Edite `otel-agent/pull.d/linux-hosts.yaml` — um item por servidor:

```yaml
static_configs:
  - targets: ["10.0.0.21:9100"]
    labels:
      host_name: "app-legado-01"          # vira host.name
      deployment_environment_name: prd    # vira deployment.environment.name
      cloud_provider: mgc                 # vira cloud.provider
      cloud_region: br-se1                # vira cloud.region
      cloud_availability_zone: a          # vira cloud.availability_zone
  - targets: ["10.0.0.22:9100"]
    labels:
      host_name: "app-legado-02"
      deployment_environment_name: prd
      cloud_provider: mgc
      cloud_region: br-se1
      cloud_availability_zone: a
```

Os labels usam `_` (sintaxe de label do Prometheus) e o template os converte
para os atributos OpenTelemetry do servidor remoto. O pipeline de pull **não**
usa o `resource_detection`: senão os dados receberiam a identidade da stack.

### 2.3 Testar a conectividade e aplicar

```bash
# A partir do servidor da stack (mesma rede usada pelo otel-agent)
curl -s -m 5 -o /dev/null -w "%{http_code}\n" http://10.0.0.21:9100/metrics   # 200

docker compose restart otel-agent
docker logs otel-agent 2>&1 | grep -E "carregando coleta pull|Everything is ready"
```

---

## 3. O que é coletado (Política Lean)

Só as métricas da lista `keep` do template — os insumos da conversão para
`system.*` (CPU, load, memória, swap, disco, filesystem, rede, boot,
`node_uname_info`, `node_os_info`) — e o `up` (disponibilidade do alvo). São
descartados pseudo-dispositivos (`loop`, `ram`, `dm-*`), pseudo-filesystems
(`tmpfs`, `overlay`...), interfaces virtuais e as séries sintéticas `scrape_*`.

A conversão (`*_node_semconv` em `otel-agent/pull-semconv.yaml`) grava os mesmos
nomes, atributos e a mesma semântica do `host_metrics` do agente — validada
contra o agente no mesmo servidor, com valores iguais (memória `used` =
MemTotal − MemAvailable, filesystem `used`/`free`/`reserved` etc.; detalhes em
[docs/METRICS.md](../../../docs/METRICS.md) §7.1). O nome do SO e o kernel vão
para o `target_info` (`os.description`), como no agente. Diferenças: o
`node_exporter` não informa se o filesystem é ro/rw (`mode=rw`) e nomeia volumes
LVM por `/dev/mapper/...`.

Referência validada (Debian 13, node_exporter 1.9.0): **46 séries** por
servidor, contra ~1.555 expostas pelo `node_exporter`.

---

## 4. Validação

A partir do servidor da stack:

```bash
H="app-legado-01"

# Alvo no ar? (1 = scrape OK)
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"up\", \"host.name\"=\"$H\"}"

# Quantidade de séries do servidor (esperado ~46)
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=count({\"host.name\"=\"$H\"})"
```

No Grafana: **Explore** → **Mimir** →
`rate({"system.cpu.time", "host.name"="app-legado-01", state!="idle"}[5m])` — ou
o dashboard **Hosts → Linux Hosts**, selecionando o servidor.

---

## Solução de problemas

**`up = 0` ou série ausente**
```bash
curl -s -m 5 http://<IP>:9100/metrics | head -3        # do servidor da stack
docker logs otel-agent 2>&1 | grep -iE "scrape|prometheus" | tail -5
```
Causas comuns: firewall do servidor remoto (seção 1.2), `node_exporter`
parado, IP/porta errados no `targets`.

**Template não carregado**
O arquivo precisa ter extensão `.yaml` e estar em `otel-agent/pull.d/`; reinicie
o `otel-agent` após qualquer alteração.

---
🔙 Voltar: [README Principal](../../../README.md)
