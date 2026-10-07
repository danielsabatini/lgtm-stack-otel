# OpenTelemetry Collector + OBI — Instalação em Servidor Linux (Modo Agent)

Guia para instalar o agente OpenTelemetry em um servidor Linux e enviar
métricas, logs e, opcionalmente, traces + métricas HTTP para o `otel-gateway`
da stack LGTM — **tudo em OTLP, com a
[OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)**.

---

## Como o agente funciona

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| **OpenTelemetry Collector Contrib** (`otelcol-contrib`, pacote oficial) | `config.yaml` → `/etc/otelcol-contrib/config.yaml` | Métricas de host (`system.*`), logs do journald (ssh, kernel, cron, systemd), identidade OTel do host e **única** saída OTLP para o Gateway (`lgtm-stack:4317`). |
| **OpenTelemetry eBPF Instrumentation** (OBI, opcional) | `obi.yaml` → `/etc/obi/obi.yaml` + `obi.service` | Auto-instrumentação eBPF: traces e métricas HTTP/gRPC/SQL (`http.server.request.duration`...) sem alterar o código. Envia OTLP ao Collector local (`127.0.0.1:4317`). |

```text
journald ─┐
host ─────┼─> otelcol-contrib ──OTLP──> otel-gateway:4317 ──> Mimir / Loki / Tempo
OBI ──────┘  (127.0.0.1:4317)
```

**Política Lean:** cada métrica e cada fonte de log do `config.yaml` é
explícita; o que não está listado não é coletado. Em teste (Debian 13, 1 vCPU)
o host gera ~66 séries de métricas `system.*`; o Collector usa ~230 MB de RSS
e o OBI ~135 MB, ambos com CPU < 1% em repouso.

---

## Pré-requisitos

- Debian / Ubuntu (ou Red Hat / Fedora), `x86_64` ou `arm64`
- Acesso root ou sudo
- Servidor LGTM com o `otel-gateway` acessível na porta **4317** (OTLP gRPC)
- `systemd` e `journalctl` (logs do journald)
- Para o OBI: kernel Linux `>= 5.8` com BTF (ver seção 6)

---

## 1. Clonar o repositório

```bash
git clone <url-do-repositorio> lgtm-stack
cd lgtm-stack/examples/push/linux
```

> Para atualizar os arquivos no futuro, basta executar `git pull` dentro
> do diretório `lgtm-stack/`.

---

## 2. Configurar resolução de nome e testar o Gateway

```bash
LGTM_IP="<IP_DO_SERVIDOR_LGTM>"
echo "$LGTM_IP  lgtm-stack" | sudo tee -a /etc/hosts

ping -c 1 lgtm-stack
timeout 3 bash -c '</dev/tcp/lgtm-stack/4317' && echo "Gateway OTLP 4317 OK"
```

---

## 3. Instalar o OpenTelemetry Collector Contrib

Use a versão homologada da stack (variável `OTELCOL_CONTRIB_VERSION` do
`.env.example` do repositório). Pacotes oficiais:
[opentelemetry-collector-releases](https://github.com/open-telemetry/opentelemetry-collector-releases/releases).

### Debian / Ubuntu

```bash
VER=<OTELCOL_CONTRIB_VERSION>          # ex.: 0.162.0
ARCH=$(dpkg --print-architecture)      # amd64 ou arm64
curl -fsSLO "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${VER}/otelcol-contrib_${VER}_linux_${ARCH}.deb"
sudo dpkg -i "otelcol-contrib_${VER}_linux_${ARCH}.deb"
```

### Red Hat / Fedora

```bash
VER=<OTELCOL_CONTRIB_VERSION>
ARCH=$(uname -m | sed 's/aarch64/arm64/; s/x86_64/amd64/')
sudo rpm -ivh "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${VER}/otelcol-contrib_${VER}_linux_${ARCH}.rpm"
```

O pacote cria o usuário `otelcol-contrib`, o serviço systemd
`otelcol-contrib` e o arquivo de ambiente
`/etc/otelcol-contrib/otelcol-contrib.conf`.

---

## 4. Identidade do host e endereço do Gateway

A identidade de **todos** os sinais (métricas, logs, traces e o self-monitoring
do agente) é definida uma única vez, no arquivo de ambiente do serviço. O
Collector é a fonte única dessa identidade: ele sobrescreve `host.name` e os
atributos abaixo inclusive nos dados do OBI.

| Variável | Uso |
|---|---|
| `OTEL_RESOURCE_ATTRIBUTES` | Variável padrão do OpenTelemetry, lida pelo detector `env`: `deployment.environment.name`, `cloud.provider`, `cloud.region`, `cloud.availability_zone`. |
| `LGTM_GATEWAY_ENDPOINT` | Endereço OTLP gRPC do Gateway (opcional, default `lgtm-stack:4317`). |

`host.name` (hostname do SO) e `os.type` vêm automaticamente do detector `system`.

```bash
sudo tee -a /etc/otelcol-contrib/otelcol-contrib.conf << 'EOF'

# Identidade OpenTelemetry deste host (OTel Semantic Conventions)
OTEL_RESOURCE_ATTRIBUTES="deployment.environment.name=prd,cloud.provider=mgc,cloud.region=br-se1,cloud.availability_zone=a"
# Gateway da stack LGTM (OTLP gRPC)
LGTM_GATEWAY_ENDPOINT=lgtm-stack:4317
EOF
```

---

## 5. Configurar e iniciar o Collector

```bash
sudo install -m 0644 ~/lgtm-stack/examples/push/linux/config.yaml /etc/otelcol-contrib/config.yaml

# Logs do journald: o usuário do serviço precisa ler o journal
sudo usermod -aG systemd-journal otelcol-contrib

# Validar (rodar a partir de / — o usuário do serviço não lê o seu $HOME)
cd / && sudo -u otelcol-contrib bash -c 'set -a; . /etc/otelcol-contrib/otelcol-contrib.conf; /usr/bin/otelcol-contrib validate --config=/etc/otelcol-contrib/config.yaml' && echo "config OK"

sudo systemctl enable otelcol-contrib
sudo systemctl restart otelcol-contrib
systemctl is-active otelcol-contrib
```

No log de partida devem aparecer as 4 fontes do journald e a mensagem final
`Everything is ready`:

```bash
sudo journalctl -u otelcol-contrib -n 30 --no-pager | grep -E "Journalctl command|Everything is ready"
```

> **O que é coletado?** Métricas `system.*` (CPU, load, memória, swap, disco,
> filesystem, rede, uptime) e logs do journald: `ssh` (todas as severidades) e
> `kernel`, `cron`, `systemd` (só `warning` ou mais grave). Política de nomes e
> labels: [docs/METRICS.md](../../../docs/METRICS.md) e
> [docs/LOGS.md](../../../docs/LOGS.md).

---

## 6. Traces e métricas HTTP com OBI (Opcional)

> Pule esta seção se este host não roda serviços HTTP/gRPC a instrumentar.
> Métricas de host e logs funcionam sem o OBI.

O [OBI](https://opentelemetry.io/docs/zero-code/obi/) (OpenTelemetry eBPF
Instrumentation) instrumenta serviços pelo kernel, sem alterar o código, e gera:

- **Traces** distribuídos, com propagação de contexto entre serviços.
- **Métricas RED** com nomes do padrão (`http.server.request.duration`,
  `http.client.request.duration`, `rpc.server.call.duration`...), calculadas
  sobre **100% do tráfego** — antes do tail sampling do Gateway, que guarda só
  5% dos traces "OK".

### Validar o kernel

```bash
uname -r                                                    # precisa ser >= 5.8
ls /sys/kernel/btf/vmlinux 2>/dev/null && echo "BTF OK"     # BTF obrigatório
```

Sem `/sys/kernel/btf/vmlinux` o OBI não inicia — não prossiga sem resolver
(geralmente exige um kernel mais recente da distribuição).

### Instalar o binário

Use a versão homologada (variável `OBI_VERSION` do `.env.example`). Releases:
[opentelemetry-ebpf-instrumentation](https://github.com/open-telemetry/opentelemetry-ebpf-instrumentation/releases).

```bash
VER=<OBI_VERSION>                                     # ex.: v0.14.0
ARCH=$(uname -m | sed 's/aarch64/arm64/; s/x86_64/amd64/')
BASE="https://github.com/open-telemetry/opentelemetry-ebpf-instrumentation/releases/download/${VER}"
cd /tmp
curl -fsSLO "${BASE}/obi-${VER}-linux-${ARCH}.tar.gz"
curl -fsSLO "${BASE}/SHA256SUMS"
sha256sum -c --ignore-missing SHA256SUMS              # deve imprimir ": OK"
mkdir -p obi && tar -xzf "obi-${VER}-linux-${ARCH}.tar.gz" -C obi
sudo install -m 0755 obi/obi /usr/local/bin/obi
```

### Usuário, configuração e serviço

O OBI roda com usuário dedicado e **apenas as capabilities eBPF necessárias**,
não como root (ver comentários em `obi.service`).

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin obi
sudo mkdir -p /etc/obi
sudo install -m 0644 ~/lgtm-stack/examples/push/linux/obi.yaml    /etc/obi/obi.yaml
sudo install -m 0644 ~/lgtm-stack/examples/push/linux/obi.service /etc/systemd/system/obi.service
```

Edite `/etc/obi/obi.yaml` e ajuste os serviços a instrumentar — um item por
serviço, sempre escopado por porta, com o nome lógico que vira `service.name`:

```yaml
discovery:
  instrument:
    - open_ports: "8080"
      name: frontend
    - open_ports: "8081"
      name: middleware
```

> **Sempre escope por porta.** Instrumentar o host inteiro sem filtro torna
> o volume de spans e a cardinalidade impossíveis de prever.
>
> **Propagação de contexto:** o bloco `ebpf: context_propagation: headers` é o
> que costura serviços que se chamam por HTTP sob um único `traceID` (o kernel
> injeta o cabeçalho W3C `traceparent`). `headers` basta para HTTP em texto
> claro; os modos `tcp`/`all` só são necessários para HTTPS e usam programas
> de Linux Traffic Control (TC), que podem conflitar com outros programas TC
> do host (ex.: Cilium).
>
> **Nunca** troque o `sampler` para um modo por ratio (`traceidratio`): o tail
> sampling do Gateway precisa ver 100% dos spans para reter todos os erros e
> lentidões.

Inicie:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now obi
systemctl is-active obi
sudo journalctl -u obi -n 50 --no-pager | grep -E "instrumenting process|level=(WARN|ERROR)"
```

Quando vários serviços usam o mesmo executável (ex.: três serviços Python),
o OBI registra `instrumenting process` uma única vez — as sondas ficam no
executável e cada processo continua recebendo o seu `service.name`.

Avisos esperados e inofensivos na partida: `timed out while waiting for Cloud
metadata` (o OBI tenta detectar EC2/Azure por ~2 s) e, em kernels recentes,
`kernel misreports ioctl(FIONREAD)... enabling BPF compensation`.

### Testar

```bash
# Gere tráfego real no serviço instrumentado (ajuste porta/rota)
for i in $(seq 1 20); do curl -s -o /dev/null http://localhost:8080/; done
```

No Grafana (**Explore**):

1. **Tempo:** `{ resource.service.name = "frontend" && resource.host.name = "<HOSTNAME>" }`.
   Confirme os resource attributes `host.name`, `deployment.environment.name`
   e `cloud.*`. Com propagação de contexto, um trace que atravessa serviços
   mostra o `CLIENT` de um processo como pai do `SERVER` do próximo, sob o
   mesmo `traceID`.
2. **Mimir (100% do tráfego):**
   `sum by ("service.name", "http.route") (rate({"http.server.request.duration", "host.name"="<HOSTNAME>"}[5m]))`.

> Traces "OK" e rápidos são amostrados a 5% pelo Gateway: com pouco tráfego é
> normal não ver nenhum no Tempo. Use uma rota que retorne erro ou demore mais
> de 1 s para validar o caminho; as métricas do OBI contam tudo.

---

## 7. Verificar o envio de dados

**Importante:** quando o envio dá certo, o Collector fica em silêncio. Uma
falha aparece explicitamente (`Exporting failed. Will retry`, `connection
refused`, `Unavailable`). Durante uma queda do Gateway o Collector guarda os
dados em fila e reenvia quando ele volta (validado com 70 s de queda, sem
perda de amostras).

Para confirmar positivamente, consulte os backends a partir do servidor LGTM
(rede interna `lgtm`):

```bash
H="<HOSTNAME_DO_SERVIDOR>"

# Métricas de host (nomes OTel: aspas obrigatórias por causa dos pontos)
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=count({\"system.cpu.time\", \"host.name\"=\"$H\"})"

# Logs do journald (no Loki os pontos viram underscore: host.name -> host_name)
docker run --rm --network lgtm curlimages/curl -sG "http://loki:3100/loki/api/v1/query_range" \
  --data-urlencode "query={host_name=\"$H\"}" --data-urlencode 'limit=5'
```

Procure por `"result":[...]` **não vazio**.

No Grafana: **Explore** → **Loki** → `{host_name="<HOSTNAME>", service_name="ssh"}`
e confira nos detalhes do log `severity_text`, `process.pid` e `category`.

> Os dashboards provisionados ainda usam os nomes Prometheus antigos e estão
> sendo refeitos sobre os nomes OpenTelemetry — até lá, valide pelo Explore.

---

## Atualizar configurações

```bash
cd ~/lgtm-stack && git pull
sudo install -m 0644 examples/push/linux/config.yaml /etc/otelcol-contrib/config.yaml
sudo systemctl restart otelcol-contrib
# OBI: reaplique seus ajustes de discovery antes de copiar o obi.yaml do repositório
```

---

## 8. Dimensionamento (Sizing)

Projeção de disco e cardinalidade por host: 👉 **[docs/SIZING.md](../../../docs/SIZING.md)**

---

## Solução de problemas

**Conectividade com o Gateway**
```bash
grep lgtm-stack /etc/hosts
timeout 3 bash -c '</dev/tcp/lgtm-stack/4317' && echo OK || echo "porta 4317 inacessível (firewall/rota)"
sudo journalctl -u otelcol-contrib --since "-5m" --no-pager | grep -E "Exporting failed|refused|Unavailable"
```

**`validate` termina com `panic: stat .: permission denied`**
Rode a partir de `/` (`cd /`): o usuário `otelcol-contrib` não tem acesso ao
diretório atual.

**Identidade errada ou ausente (`deployment.environment.name`, `cloud.*`)**
```bash
grep -E "OTEL_RESOURCE_ATTRIBUTES|LGTM_GATEWAY_ENDPOINT" /etc/otelcol-contrib/otelcol-contrib.conf
sudo systemctl restart otelcol-contrib
```

**Logs do journal não aparecem**
```bash
groups otelcol-contrib                 # deve conter systemd-journal
sudo systemctl restart otelcol-contrib  # obrigatório após incluir no grupo
```

**OBI não inicia / erros de permissão**
```bash
sudo journalctl -u obi -n 100 --no-pager | grep -iE "bpf|permission|capabilit|error"
systemctl cat obi | grep -E "Capabilit|ExecStartPre"
```
Causas comuns: kernel sem BTF ou `< 5.8` (sem workaround); capability
removida da unit; `ExecStartPre` do bpffs ausente (gera
`mkdir /sys/fs/bpf/otel: permission denied`).

**Nenhum trace no Tempo**
- `sudo ss -tlnp | grep <porta>` — a porta em `open_ports` deve ser a do processo.
- Gere tráfego real durante a observação (o OBI só vê requisições que passam
  pela porta).
- Lembre do tail sampling (5% dos traces "OK"); confira as métricas
  `http.server.request.duration`, que contam tudo.
