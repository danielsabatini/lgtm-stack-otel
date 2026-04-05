# LGTM Stack

Stack de observabilidade completa baseada em componentes open-source da Grafana Labs. Coleta **métricas**, **logs** e **traces** de forma integrada, com correlação nativa entre os três sinais.

## Componentes

| Serviço | Função | Porta |
|---|---|---|
| [Grafana](https://grafana.com/grafana/) | Visualização e alertas | `3000` |
| [Alloy](https://grafana.com/docs/alloy/) | Coletor (metrics/logs/traces) | `12345` · `4317` · `4318` |
| [Loki](https://grafana.com/docs/loki/) | Armazenamento de logs | `3100` |
| [Mimir](https://grafana.com/docs/mimir/) | Armazenamento de métricas | `9009` |
| [Tempo](https://grafana.com/docs/tempo/) | Armazenamento de traces | `3200` |

## Arquitetura

```
Aplicações / Host
       │
       ▼
  ┌─────────┐   OTLP gRPC/HTTP (4317/4318)
  │  Alloy  │──────────────────────────────┐
  └────┬────┘                              │
       │                                   │
  ┌────▼────┐   ┌──────────┐   ┌──────────▼──┐
  │  Loki   │   │  Mimir   │   │    Tempo    │
  │  Logs   │   │ Metrics  │   │   Traces    │
  └────┬────┘   └────┬─────┘   └──────┬──────┘
       │              │                │
       └──────────────▼────────────────┘
                  ┌─────────┐
                  │ Grafana │
                  └─────────┘
```

**Alloy** coleta automaticamente:
- Métricas do host (CPU, memória, disco, rede) via `node_exporter` embutido
- Logs do systemd journal
- Traces e métricas de aplicações via OTLP (portas `4317`/`4318`)

---

## Versões

| Imagem | Versão |
|---|---|
| `grafana/grafana` | `12.4.2` |
| `grafana/alloy` | `1.15.0` |
| `grafana/loki` | `3.7.1` |
| `grafana/mimir` | `3.0.5` |
| `grafana/tempo` | `2.10.3` |

---

## Retenção de Dados

Controlada por variáveis de ambiente no arquivo `.env`, sem necessidade de editar os arquivos de configuração de cada produto.

| Variável | Backend | Padrão | Formato aceito |
|---|---|---|---|
| `LOKI_RETENTION` | Loki (logs) | `30d` | `24h`, `7d`, `30d`, `1y` |
| `MIMIR_RETENTION` | Mimir (métricas) | `30d` | `24h`, `7d`, `30d`, `1y` |
| `TEMPO_RETENTION` | Tempo (traces) | `336h` | somente horas: `24h`, `168h`, `336h` |

**Exemplo** — alterar retenção no `.env`:

```dotenv
LOKI_RETENTION=90d
MIMIR_RETENTION=90d
TEMPO_RETENTION=720h   # 30 dias em horas
```

Aplique a alteração sem derrubar o stack:

```bash
docker compose up -d loki mimir tempo
```

---

## Dimensionamento de Discos

Antes de provisionar o armazenamento, estime o tamanho de cada disco com base no seu ambiente real. Os dados abaixo são derivados da documentação oficial da Grafana Labs.

### O que determina o uso de disco

| Backend | Driver de armazenamento |
|---|---|
| **Mimir** | Número de séries ativas (métricas únicas em coleta) |
| **Loki** | Volume de logs brutos ingeridos por dia |
| **Tempo** | Número de spans ingeridos por dia |
| **Grafana** | Fixo — SQLite, dashboards JSON, plugins |
| **Alloy** | Fixo — WAL buffer temporário (dados em trânsito) |

---

### Mimir — Métricas

**Referência oficial:** 2 bytes/amostra em blocos compactados.
Com `scrape_interval=60s` (configurado neste stack): 1.440 amostras/dia por série ≈ **3 KB/série/dia**.

```
disco (GB) = séries_ativas × dias_retenção × 0.0000045 × 1.5
```

| Séries ativas | 30 dias | 60 dias | 90 dias |
|---|---|---|---|
| 5.000 | ~1 GB | ~2 GB | ~3 GB |
| 20.000 | ~4 GB | ~8 GB | ~12 GB |
| 100.000 | ~20 GB | ~41 GB | ~61 GB |
| 500.000 | ~101 GB | ~203 GB | ~304 GB |

> Este stack coleta ~800 séries do host por padrão. Para estimar as séries das aplicações, use `count({__name__=~".+"})` no Grafana após alguns minutos de ingestão.

---

### Loki — Logs

**Referência:** compressão típica de 10:1 (texto bruto → TSDB comprimido). Fator de overhead para índice e WAL: 1,5×.

```
disco (GB) = GB_bruto_por_dia × 0.1 × dias_retenção × 1.5
```

| Logs brutos/dia | 30 dias | 60 dias | 90 dias |
|---|---|---|---|
| 1 GB | ~4,5 GB | ~9 GB | ~13,5 GB |
| 5 GB | ~22 GB | ~45 GB | ~67 GB |
| 20 GB | ~90 GB | ~180 GB | ~270 GB |
| 100 GB | ~450 GB | ~900 GB | — |

> Para estimar o volume de logs do seu ambiente, rode por 1 hora e consulte `sum(rate(loki_ingester_bytes_received_total[1h]))` no Grafana.

---

### Tempo — Traces

**Referência oficial:** `bytes_ingeridos/dia × dias_retenção`. Tamanho médio por span: ~1,5 KB (varia com atributos customizados).

```
disco (GB) = spans_por_dia × 0.0000015 × dias_retenção × 1.3
```

| Spans/dia | 14 dias | 30 dias | 60 dias |
|---|---|---|---|
| 100 mil | ~0,3 GB | ~0,6 GB | ~1,2 GB |
| 1 milhão | ~2,7 GB | ~5,8 GB | ~11,7 GB |
| 10 milhões | ~27 GB | ~58 GB | ~117 GB |
| 100 milhões | ~273 GB | ~585 GB | — |

> Para ambientes sem tracing ainda, comece com 20 GB e monitore com `tempo_ingester_bytes_received_total`.

---

### Grafana e Alloy — Uso Fixo e Previsível

| Serviço | O que armazena | Tamanho típico |
|---|---|---|
| **Grafana** | SQLite, dashboards JSON, plugins | < 1 GB |
| **Alloy** | WAL buffer (dados em trânsito para Loki/Mimir/Tempo) | < 2 GB |

Por serem fixos e pequenos, **Grafana e Alloy compartilham um único LV** em um disco dedicado de pequeno porte (`vdc`), mantendo isolamento sem desperdiçar um disco de dados completo.

---

### Exemplo de Dimensionamento Completo

Ambiente médio: 20.000 séries · 5 GB de logs/dia · 1 M spans/dia · retenção padrão (30d logs/métricas, 14d traces):

| Disco | Componente | Cálculo | Tamanho sugerido |
|---|---|---|---|
| `vdb` | Engine Docker | fixo | 40 GB |
| `vdc` | Grafana + Alloy | fixo | 10 GB |
| `vdd` | Loki | 22 GB × 1,3 | **30 GB** |
| `vde` | Mimir | 8 GB × 1,3 | **12 GB** |
| `vdf` | Tempo | 2,7 GB × 1,3 | **8 GB** |

> Adicione sempre 30% de margem ao resultado das fórmulas para absorver crescimento e picos: `disco_final = resultado × 1.3`

---

## Setup — Produção (com LVM)

Guia para servidor com discos físicos dedicados. Para um ambiente de desenvolvimento rápido, veja a seção [Desenvolvimento Local](#desenvolvimento-local).

### 1. Instalar Docker

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2

# Impede que o Docker inicie antes da configuração estar completa
sudo systemctl mask docker.service docker.socket
```

### 2. Preparar os Discos (LVM)

Mapeamento para cinco discos. Cada backend de dados tem isolamento físico total; Grafana e Alloy compartilham um disco de pequeno porte.

> **Adapte os nomes dos discos ao seu ambiente.** Os nomes `vdb`, `vdc`... são exemplos para VMs com discos virtio. Use `lsblk` para identificar os discos reais antes de executar qualquer comando.

| Disco | Ponto de Montagem | Conteúdo |
|---|---|---|
| `vdb` | `/docker` | Engine Docker |
| `vdc` | `/lgtm/apps` | Grafana · Alloy WAL |
| `vdd` | `/lgtm/loki` | Logs (Loki) |
| `vde` | `/lgtm/mimir` | Métricas (Mimir) |
| `vdf` | `/lgtm/tempo` | Traces (Tempo) |

**Identificar os discos disponíveis:**

```bash
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
```

**Criar Physical Volumes:**

```bash
sudo pvcreate /dev/vdb /dev/vdc /dev/vdd /dev/vde /dev/vdf
```

**Criar Volume Groups e Logical Volumes:**

```bash
# Engine Docker (disco vdb)
sudo vgcreate vg_docker /dev/vdb
sudo lvcreate -l 100%FREE -n lv_docker vg_docker

# Grafana + Alloy WAL (disco vdc)
# 100%FREE de um disco pequeno (~10 GB) é mais que suficiente:
# Grafana < 1 GB, Alloy WAL < 2 GB
sudo vgcreate vg_apps /dev/vdc
sudo lvcreate -l 100%FREE -n lv_apps vg_apps

# Loki (disco vdd) — dimensione conforme a seção acima
sudo vgcreate vg_loki /dev/vdd
sudo lvcreate -l 100%FREE -n lv_loki vg_loki

# Mimir (disco vde) — dimensione conforme a seção acima
sudo vgcreate vg_mimir /dev/vde
sudo lvcreate -l 100%FREE -n lv_mimir vg_mimir

# Tempo (disco vdf) — dimensione conforme a seção acima
sudo vgcreate vg_tempo /dev/vdf
sudo lvcreate -l 100%FREE -n lv_tempo vg_tempo
```

### 3. Formatar e Montar

```bash
sudo mkfs.ext4 /dev/vg_docker/lv_docker
sudo mkfs.ext4 /dev/vg_apps/lv_apps
sudo mkfs.ext4 /dev/vg_loki/lv_loki
sudo mkfs.ext4 /dev/vg_mimir/lv_mimir
sudo mkfs.ext4 /dev/vg_tempo/lv_tempo

sudo mkdir -p /docker /lgtm/apps/grafana /lgtm/apps/alloy /lgtm/loki /lgtm/mimir /lgtm/tempo

cat <<EOF | sudo tee -a /etc/fstab
/dev/mapper/vg_docker-lv_docker  /docker     ext4  defaults  0 2
/dev/mapper/vg_apps-lv_apps      /lgtm/apps  ext4  defaults  0 2
/dev/mapper/vg_loki-lv_loki      /lgtm/loki  ext4  defaults  0 2
/dev/mapper/vg_mimir-lv_mimir    /lgtm/mimir ext4  defaults  0 2
/dev/mapper/vg_tempo-lv_tempo    /lgtm/tempo ext4  defaults  0 2
EOF

sudo mount -a

# Garante que os subdiretórios existam após a montagem do lv_apps
sudo mkdir -p /lgtm/apps/grafana /lgtm/apps/alloy
```

### 4. Configurar Docker (Data-Root)

```bash
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "data-root": "/docker",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
```

### 5. Corrigir Permissões (UIDs Oficiais)

Os containers rodam com UIDs específicos. As permissões dos diretórios devem bater.

```bash
# Grafana — UID 472, GID 0 (root group, conforme Dockerfile oficial)
sudo chown -R 472:0 /lgtm/apps/grafana

# Loki, Mimir e Tempo — UID/GID 10001
sudo chown -R 10001:10001 /lgtm/loki /lgtm/mimir /lgtm/tempo

# Alloy — sem chown (roda como root com privileged)
```

### 6. Ativar Docker

```bash
sudo systemctl unmask docker.service docker.socket
sudo systemctl enable --now docker.service docker.socket

# Validar
docker info | grep "Docker Root Dir"
# Esperado: Docker Root Dir: /docker
```

### 7. Criar Volumes Docker

```bash
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/grafana --opt o=bind grafana-data
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/alloy   --opt o=bind alloy-data
docker volume create --driver local --opt type=none --opt device=/lgtm/loki         --opt o=bind loki-data
docker volume create --driver local --opt type=none --opt device=/lgtm/mimir        --opt o=bind mimir-data
docker volume create --driver local --opt type=none --opt device=/lgtm/tempo        --opt o=bind tempo-data
```

### 8. Subir o Stack

```bash
# Clone o repositório
git clone <url-do-repositorio> /opt/lgtm-stack
cd /opt/lgtm-stack

# Configure as credenciais do Grafana
cp .env.example .env
# Edite o .env com seu editor preferido

# Suba o stack
docker compose up -d
```

---

## Desenvolvimento Local

Para testar sem LVM, basta criar volumes Docker simples antes de subir:

```bash
docker volume create grafana-data
docker volume create loki-data
docker volume create mimir-data
docker volume create tempo-data
docker volume create alloy-data

cp .env.example .env
docker compose up -d
```

> **Nota:** Neste modo o Alloy não consegue ler o journal do systemd caso o host não use systemd (ex: WSL2, macOS). As métricas do host e os traces via OTLP continuarão funcionando normalmente.

---

## Acessar os Serviços

Após `docker compose up -d`, aguarde todos os containers ficarem `healthy`:

```bash
docker compose ps
```

| Serviço | URL | Credenciais |
|---|---|---|
| Grafana | http://localhost:3000 | `admin` / valor de `GF_ADMIN_PASSWORD` |
| Alloy UI | http://localhost:12345 | — |
| Loki | http://localhost:3100/ready | — |
| Mimir | http://localhost:9009/ready | — |
| Tempo | http://localhost:3200/ready | — |

---

## Dashboards

Os datasources Loki, Mimir e Tempo são provisionados automaticamente com correlação entre sinais (Log → Trace → Metrics).

Os dashboards abaixo já estão incluídos no repositório e carregados automaticamente ao subir o stack:

| Pasta no Grafana | Dashboard | Fonte |
|---|---|---|
| **Host** | Node Exporter Full | [1860](https://grafana.com/grafana/dashboards/1860) |
| **Stack** | Logging Dashboard via Loki | [12611](https://grafana.com/grafana/dashboards/12611) |
| **Stack** | Alloy Monitoring | [20475](https://grafana.com/grafana/dashboards/20475) |

**Adicionar novos dashboards:**

1. Baixe o JSON em [grafana.com/grafana/dashboards](https://grafana.com/grafana/dashboards/)
2. Substitua placeholders de datasource pelos UIDs provisionados: `mimir`, `loki`, `tempo`
3. Salve em `grafana/provisioning/dashboards/<Pasta>/nome.json`
4. O Grafana recarrega automaticamente a cada 30s (ou `docker compose restart grafana`)

---

## Enviar Traces e Métricas de Aplicações

O Alloy expõe um endpoint OTLP para receber dados diretamente das suas aplicações:

| Protocolo | Endpoint |
|---|---|
| gRPC | `http://<host>:4317` |
| HTTP | `http://<host>:4318` |

Exemplo com OpenTelemetry SDK (Go):

```go
exporter, _ := otlptracegrpc.New(ctx,
    otlptracegrpc.WithEndpoint("localhost:4317"),
    otlptracegrpc.WithInsecure(),
)
```

---

## Manutenção

**Ver logs de um serviço:**
```bash
docker compose logs -f loki
```

**Reiniciar um serviço sem derrubar o stack:**
```bash
docker compose restart mimir
```

**Atualizar imagens:**
```bash
docker compose pull
docker compose up -d
```

**Parar e remover containers (dados preservados nos volumes):**
```bash
docker compose down
```

---

## Mapeamento Final de Recursos (Produção)

| Recurso | Disco | VG / LV | Ponto de Montagem |
|---|---|---|---|
| Engine Docker | `vdb` | `vg_docker-lv_docker` | `/docker` |
| Grafana + Alloy | `vdc` | `vg_apps-lv_apps` | `/lgtm/apps` |
| Loki Logs | `vdd` | `vg_loki-lv_loki` | `/lgtm/loki` |
| Mimir Metrics | `vde` | `vg_mimir-lv_mimir` | `/lgtm/mimir` |
| Tempo Traces | `vdf` | `vg_tempo-lv_tempo` | `/lgtm/tempo` |
