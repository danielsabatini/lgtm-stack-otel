# Coleta Remota — Cluster DNS Interno (CoreDNS + etcd + node_exporter)

Monitoramento dos **3 nós do cluster de DNS interno**. Cada nó expõe três
exporters; o `otel-agent` da stack faz o scrape, converte para OTLP com a
identidade OpenTelemetry de cada nó e envia ao `otel-gateway` (que continua só
OTLP).

```text
nó DNS (x3)                                       servidor da stack LGTM
:9100/metrics  node_exporter (SO)        <──┐
:9153/metrics  CoreDNS (resolução DNS)   <──┼─scrape── otel-agent ──OTLP──> otel-gateway
:2379/metrics  etcd (backend do CoreDNS) <──┘
```

| Porta | Exporter | Job / `service.name` |
|---|---|---|
| `9100` | node_exporter | `node-exporter` |
| `9153` | CoreDNS | `coredns` |
| `2379` | etcd | `etcd` |

Validado contra o cluster `dns-se1-1/2/3` (Magalu Cloud, br-se1, zonas a/b/c):
CoreDNS (Go 1.26.5), etcd 3.7, Ubuntu 24.04 (kernel 6.8).

---

## 1. Conectividade

O servidor da stack precisa alcançar as portas `9100`, `9153` e `2379` de cada
nó (mesma VPC, peering ou VPN). Teste a partir do servidor da stack:

```bash
for ip in 172.18.1.2 172.18.17.2 172.18.33.2; do
  for p in 9100 9153 2379; do
    printf "%-12s :%-5s %s\n" "$ip" "$p" "$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://$ip:$p/metrics)"
  done
done
# esperado: 200 em todas
```

Os endpoints são HTTP sem autenticação: mantenha essas portas acessíveis
**somente** a partir da rede da stack (security group / firewall dos nós). A
`2379` também é a API cliente do etcd — nunca a exponha além da rede da stack.

> **Sem rota direta (laboratório):** use um proxy SOCKS pelo bastion
> (`ssh -f -N -D 127.0.0.1:11080 <bastion>`) e acrescente em cada job do
> template `proxy_url: socks5://host.docker.internal:11080` — o scrape continua
> usando os IPs reais dos nós. Alternativa por porta: `artifacts/scripts/dns-tunnels.sh`.

---

## 2. Configurar o otel-agent

```bash
cd /caminho/para/lgtm-stack
cp examples/pull/dns/dns-hosts.yaml otel-agent/pull.d/dns-hosts.yaml
```

Edite `otel-agent/pull.d/dns-hosts.yaml`. Os nós são declarados **uma única
vez** (âncora `&dns_nodes` no job `node-exporter`) e reaproveitados pelos jobs
`coredns` e `etcd`, que só trocam a porta. Informe o IP **sem porta**:

```yaml
static_configs: &dns_nodes
  - targets: ["172.18.1.2"]
    labels:
      host_name: "dns-se1-1"              # vira host.name
      deployment_environment_name: prd    # vira deployment.environment.name
      cloud_provider: mgc                 # vira cloud.provider
      cloud_region: br-se1                # vira cloud.region
      cloud_availability_zone: a          # vira cloud.availability_zone
  - targets: ["172.18.17.2"]
    labels: { host_name: "dns-se1-2", deployment_environment_name: prd, cloud_provider: mgc, cloud_region: br-se1, cloud_availability_zone: b }
  - targets: ["172.18.33.2"]
    labels: { host_name: "dns-se1-3", deployment_environment_name: prd, cloud_provider: mgc, cloud_region: br-se1, cloud_availability_zone: c }
```

Aplique:

```bash
docker compose restart otel-agent
docker logs otel-agent 2>&1 | grep -E "carregando coleta pull|Everything is ready"
```

O arquivo em `otel-agent/pull.d/` contém IPs do ambiente e não é versionado.

---

## 3. O que é coletado (Política Lean)

| Exporter | Allowlist | Séries (3 nós, referência) |
|---|---|---|
| node_exporter → `system.*` | mesma de [examples/pull/linux](../linux/INSTALL.md) + `up`; convertida para o formato do agente (`*_node_semconv`) | ~150 |
| CoreDNS | build/plugins, processo (fds, memória), panics, reloads, requests/responses, latência, cache, forward/proxy + `up` | 157 |
| etcd | liderança (`has_leader`, `is_leader`, trocas), propostas, versões, quota/tamanho do banco, chaves, latência de WAL fsync, backend commit e RTT entre peers + `up` | 57 |

As séries sintéticas `scrape_*` e pseudo-dispositivos/filesystems são
descartados. O SO dos nós é gravado como `system.*` (o mesmo formato do agente);
CoreDNS e etcd não têm OTel Semantic Conventions e mantêm os nomes dos
exporters.

### Histogramas de latência (mudança em relação ao modelo legado)

Os histogramas do CoreDNS e do etcd chegam ao Mimir como **native histograms**:
o nome fica **sem** `_bucket`, `_sum` e `_count`, com uma série por histograma.

| Antes (Prometheus) | Agora (OTLP → native histogram) |
|---|---|
| `histogram_quantile(0.99, sum by (le, instance) (rate(coredns_dns_request_duration_seconds_bucket[5m])))` | `histogram_quantile(0.99, sum by ("host.name") (rate({"coredns_dns_request_duration_seconds"}[5m])))` |
| `rate(coredns_dns_request_duration_seconds_count[5m])` | `histogram_count(rate({"coredns_dns_request_duration_seconds"}[5m]))` |

Com o cluster ocioso (nenhuma consulta na janela), `histogram_quantile`
retorna `NaN` — é o esperado (0/0), não falha de coleta.

---

## 4. Validação

```bash
# Os 9 alvos (3 nós x 3 exporters) devem estar com up = 1
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode 'query=count({"up", "host.name"=~"dns-se1-.*"} == 1)'

# Exatamente um líder no etcd
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode 'query=sum({"etcd_server_is_leader", "host.name"=~"dns-se1-.*"})'
```

Abra o dashboard **`DNS > MGC Internal DNS`** no Grafana: linha Linux
(`system.*`, as mesmas abas do Linux Hosts), CoreDNS e etcd (histogramas
nativos), com o nó selecionado na variável `host`.

---

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| `up = 0` em um exporter de um nó | Porta bloqueada no firewall do nó ou serviço parado (`systemctl status coredns etcd prometheus-node-exporter`) |
| `up = 0` nos três exporters de um nó | Nó fora do ar ou sem rota a partir da stack |
| Soma de `etcd_server_is_leader` diferente de 1 | Cluster sem quórum ou em eleição — verificar `etcdctl endpoint status --cluster` |
| p99 `NaN` | Nenhuma consulta DNS na janela (cluster ocioso) |

---
🔙 Voltar: [README Principal](../../../README.md)
