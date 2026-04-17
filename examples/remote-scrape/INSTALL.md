# Coleta Remota via Pull — Guia de Instalação

Guia para adicionar servidores remotos ao `alloy-gateway` usando o modelo Pull
(scrape direto no exporter). Indicado para servidores onde não é possível instalar
o Alloy agent (modo Push).

---

## Como funciona

```
Servidor remoto                   Servidor LGTM
┌─────────────────┐               ┌──────────────────────────────┐
│  node_exporter  │◄── HTTP GET ──│  alloy-gateway               │
│  :9100          │               │  (conf.d/pull-legacy-*.alloy)│
└─────────────────┘               │         │                    │
                                  │         ▼                    │
                                  │       Mimir                  │
                                  └──────────────────────────────┘
```

O `alloy-gateway` faz scrape ativo nos exporters instalados nos servidores remotos,
filtra as métricas via regex e encaminha para o Mimir. Os labels de identidade
(`instance`, `environment`, `cloud_provider`, etc.) são definidos diretamente nos
targets, pois o gateway não possui as variáveis de ambiente do agente.

**Limitação — Logs:** exporters padrão não expõem logs. Para coletar SSH, kernel,
cron e systemd, instale o Alloy agent seguindo `examples/linux/INSTALL.md`.

---

## Pré-requisito no servidor LGTM

O arquivo `001-metric-gtw-local.alloy` (já presente em `alloy-gateway/conf.d/`)
define o componente `prometheus.remote_write "mimir"` que todos os arquivos de pull
abaixo referenciam. Não remova esse arquivo.

---

## Adicionar um servidor — passo a passo

### 1. Instalar o exporter no servidor remoto

Consulte a seção do exporter correspondente abaixo.

### 2. Editar o arquivo de template

Abra o arquivo de template em `examples/remote-scrape/` e ajuste a lista `targets`:

- `__address__`: IP e porta do exporter
- `instance`: nome legível do servidor (aparece nos dashboards)
- `environment`: `prd`, `stg`, `dev`, `hml`, etc.
- `cloud_provider`: `aws`, `gcp`, `azure`, `mgc`, `on-premise`, etc.
- `cloud_region`: ex. `br-se1`, `us-east-1`
- `cloud_availability_zone`: `a`, `b`, `c`, etc.

Adicione um bloco por servidor:

```alloy
targets = [
  {
    "__address__"             = "192.168.10.55:9100",
    "instance"                = "servidor-financas-01",
    "environment"             = "prd",
    "cloud_provider"          = "mgc",
    "cloud_region"            = "br-se1",
    "cloud_availability_zone" = "a",
  },
  {
    "__address__"             = "192.168.10.56:9100",
    "instance"                = "servidor-erp-legado",
    "environment"             = "prd",
    "cloud_provider"          = "mgc",
    "cloud_region"            = "br-se1",
    "cloud_availability_zone" = "a",
  },
]
```

### 3. Copiar para o conf.d do gateway

No servidor LGTM, dentro do repositório:

```bash
cp examples/remote-scrape/pull-legacy-<tipo>.alloy alloy-gateway/conf.d/
```

### 4. Reiniciar o gateway

```bash
docker compose restart alloy-gateway
```

### 5. Verificar conectividade e coleta

```bash
# Verificar logs do gateway em tempo real
docker compose logs -f alloy-gateway

# Confirmar métricas no Mimir (substitua <instance> pelo valor definido em targets)
docker exec grafana curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode 'query=up{instance="<instance>"}' | jq '.data.result'
```

---

## Linux — `pull-legacy-linux.alloy`

**Arquivo:** `examples/remote-scrape/pull-legacy-linux.alloy`
**Porta padrão:** `9100`

### Instalar o node_exporter no servidor remoto

#### Debian / Ubuntu

```bash
# Baixar a versão mais recente (ajuste a versão se necessário)
NODE_VERSION="1.9.1"
wget https://github.com/prometheus/node_exporter/releases/download/v${NODE_VERSION}/node_exporter-${NODE_VERSION}.linux-amd64.tar.gz
tar xzf node_exporter-${NODE_VERSION}.linux-amd64.tar.gz
sudo mv node_exporter-${NODE_VERSION}.linux-amd64/node_exporter /usr/local/bin/
```

#### Criar serviço systemd

```bash
sudo tee /etc/systemd/system/node_exporter.service << 'EOF'
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
User=nobody
ExecStart=/usr/local/bin/node_exporter
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter
```

#### Verificar

```bash
curl -s http://localhost:9100/metrics | head -5
```

### Métricas coletadas

| Grupo | Exemplos |
|-------|---------|
| CPU | `node_cpu_seconds_total` |
| Memória | `node_memory_MemTotal_bytes`, `node_memory_SwapFree_bytes` |
| Disco | `node_disk_read_bytes_total`, `node_disk_io_time_seconds_total` |
| Filesystem | `node_filesystem_avail_bytes`, `node_filesystem_size_bytes` |
| Rede | `node_network_receive_bytes_total`, `node_network_transmit_bytes_total` |
| Sistema | `node_load1`, `node_uname_info`, `node_os_info`, `node_boot_time_seconds` |
| Pressão (PSI) | `node_pressure_cpu_waiting_seconds_total`, `node_pressure_io_*`, `node_pressure_memory_*` |

> **PSI requer kernel ≥ 4.20.** Em kernels mais antigos as métricas `node_pressure_*`
> simplesmente não aparecem — nenhum erro é gerado.

### Labels automáticos — Sistema Operacional e Arquitetura

O pull-legacy-linux.alloy extrai automaticamente informações do servidor como labels, 
permitindo filtrar métricas no Grafana:

| Label | Fonte | Valor de exemplo |
|-------|-------|------------------|
| `os` | `node_uname_info` | `"Linux"` |
| `architecture` | `node_uname_info` | `"x86_64"`, `"aarch64"` |
| `kernel_release` | `node_uname_info` | `"6.12.74+deb13+1-amd64"` |

Esses labels são extraídos automaticamente da métrica `node_uname_info` e não requerem
configuração adicional. Estão disponíveis para filtragem em todas as métricas do servidor.

---

## Windows — `pull-legacy-windows.alloy`

**Arquivo:** `examples/remote-scrape/pull-legacy-windows.alloy`
**Porta padrão:** `9182`

### Instalar o windows_exporter no servidor remoto

1. Baixe o instalador MSI em:
   `https://github.com/prometheus-community/windows_exporter/releases`

2. Execute o instalador com os collectors necessários:

```powershell
# PowerShell (executar como Administrador)
$version = "0.30.4"
$url = "https://github.com/prometheus-community/windows_exporter/releases/download/v$version/windows_exporter-$version-amd64.msi"
Invoke-WebRequest -Uri $url -OutFile windows_exporter.msi

msiexec /i windows_exporter.msi `
  ENABLED_COLLECTORS="cpu,logical_disk,net,os,system,memory" `
  /qn
```

3. O serviço `windows_exporter` sobe automaticamente na porta `9182`.

#### Verificar

```powershell
Invoke-WebRequest -Uri http://localhost:9182/metrics -UseBasicParsing | Select-Object -First 5
```

Ou em outro host:

```bash
curl -s http://<IP>:9182/metrics | head -5
```

### Métricas coletadas

| Grupo | Prefixo |
|-------|---------|
| CPU | `windows_cpu_*` |
| Disco | `windows_logical_disk_*` |
| Rede | `windows_net_*` |
| Sistema operacional | `windows_os_*` |
| Sistema | `windows_system_*` |
| Memória | `windows_memory_*` |

### Labels automáticos — Sistema Operacional

O pull-legacy-windows.alloy extrai automaticamente informações do servidor Windows como labels,
permitindo filtrar métricas no Grafana:

| Label | Fonte | Valor de exemplo |
|-------|-------|------------------|
| `os` | `windows_os_info` | `"windows"` |
| `os_product` | `windows_os_info` | `"Windows Server 2019"` |
| `os_release` | `windows_os_info` | `"10.0.17763"` |
| `os_version` | `windows_os_info` | `"17763"` |

Esses labels são extraídos automaticamente da métrica `windows_os_info` e não requerem
configuração adicional. Estão disponíveis para filtragem em todas as métricas do servidor.

### Firewall

```powershell
New-NetFirewallRule -DisplayName "windows_exporter" -Direction Inbound `
  -Protocol TCP -LocalPort 9182 -Action Allow
```

---

## MySQL — `pull-legacy-mysql.alloy`

**Arquivo:** `examples/remote-scrape/pull-legacy-mysql.alloy`
**Porta padrão:** `9104`

### Instalar o mysqld_exporter no servidor remoto

#### Criar usuário de monitoramento no MySQL

```sql
CREATE USER 'exporter'@'localhost' IDENTIFIED BY '<senha-forte>' WITH MAX_USER_CONNECTIONS 3;
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'localhost';
FLUSH PRIVILEGES;
```

#### Instalar o exporter

```bash
MYSQL_EXP_VERSION="0.17.2"
wget https://github.com/prometheus/mysqld_exporter/releases/download/v${MYSQL_EXP_VERSION}/mysqld_exporter-${MYSQL_EXP_VERSION}.linux-amd64.tar.gz
tar xzf mysqld_exporter-${MYSQL_EXP_VERSION}.linux-amd64.tar.gz
sudo mv mysqld_exporter-${MYSQL_EXP_VERSION}.linux-amd64/mysqld_exporter /usr/local/bin/
```

#### Configurar credenciais

```bash
sudo tee /etc/mysqld_exporter.cnf << 'EOF'
[client]
user=exporter
password=<senha-forte>
host=localhost
EOF
sudo chmod 600 /etc/mysqld_exporter.cnf
```

#### Criar serviço systemd

```bash
sudo tee /etc/systemd/system/mysqld_exporter.service << 'EOF'
[Unit]
Description=Prometheus MySQL Exporter
After=network.target mysql.service

[Service]
User=nobody
ExecStart=/usr/local/bin/mysqld_exporter \
  --config.my-cnf=/etc/mysqld_exporter.cnf \
  --collect.global_status \
  --collect.global_variables \
  --collect.info_schema.innodb_metrics
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now mysqld_exporter
```

#### Verificar

```bash
curl -s http://localhost:9104/metrics | head -5
```

### Métricas coletadas

| Grupo | Prefixo |
|-------|---------|
| Status global | `mysql_global_status_*` |
| Variáveis globais | `mysql_global_variables_*` |
| InnoDB | `mysql_innodb_*` |

---

## PostgreSQL — `pull-legacy-postgresql.alloy`

**Arquivo:** `examples/remote-scrape/pull-legacy-postgresql.alloy`
**Porta padrão:** `9187`

### Instalar o postgres_exporter no servidor remoto

#### Criar usuário de monitoramento no PostgreSQL

```sql
CREATE USER exporter WITH PASSWORD '<senha-forte>';
GRANT pg_monitor TO exporter;
```

#### Instalar o exporter

```bash
PG_EXP_VERSION="0.17.1"
wget https://github.com/prometheus-community/postgres_exporter/releases/download/v${PG_EXP_VERSION}/postgres_exporter-${PG_EXP_VERSION}.linux-amd64.tar.gz
tar xzf postgres_exporter-${PG_EXP_VERSION}.linux-amd64.tar.gz
sudo mv postgres_exporter-${PG_EXP_VERSION}.linux-amd64/postgres_exporter /usr/local/bin/
```

#### Criar serviço systemd

```bash
sudo tee /etc/systemd/system/postgres_exporter.service << 'EOF'
[Unit]
Description=Prometheus PostgreSQL Exporter
After=network.target postgresql.service

[Service]
User=nobody
Environment="DATA_SOURCE_NAME=postgresql://exporter:<senha-forte>@localhost:5432/postgres?sslmode=disable"
ExecStart=/usr/local/bin/postgres_exporter \
  --collector.database \
  --collector.locks \
  --collector.stat_user_tables
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now postgres_exporter
```

#### Verificar

```bash
curl -s http://localhost:9187/metrics | head -5
```

### Métricas coletadas

| Grupo | Prefixo |
|-------|---------|
| Bancos de dados | `pg_database_*` |
| Locks | `pg_locks_*` |
| Tabelas de usuário | `pg_stat_user_tables_*` |

---

## SQL Server — `pull-legacy-sqlserver.alloy`

**Arquivo:** `examples/remote-scrape/pull-legacy-sqlserver.alloy`
**Porta padrão:** `9375`

### Instalar o sql_exporter no servidor remoto

O [sql_exporter](https://github.com/burningalchemist/sql_exporter) é o exporter
recomendado para SQL Server (suporta autenticação Windows e SQL).

#### Windows (PowerShell — Administrador)

```powershell
$version = "0.16.0"
$url = "https://github.com/burningalchemist/sql_exporter/releases/download/$version/sql_exporter-$version-windows-amd64.zip"
Invoke-WebRequest -Uri $url -OutFile sql_exporter.zip
Expand-Archive sql_exporter.zip -DestinationPath "C:\sql_exporter"
```

#### Configurar conexão com o SQL Server

Edite `C:\sql_exporter\sql_exporter.yml`:

```yaml
global:
  scrape_timeout: 10s

target:
  # Autenticação Windows (Integrated Security)
  data_source_name: "sqlserver://localhost?database=master&trusted_connection=yes"
  # Autenticação SQL Server (alternativa):
  # data_source_name: "sqlserver://exporter:<senha>@localhost?database=master"

  collectors:
    - mssql_standard
```

#### Instalar como serviço Windows

```powershell
sc.exe create sql_exporter `
  binPath= "C:\sql_exporter\sql_exporter.exe --config.file=C:\sql_exporter\sql_exporter.yml" `
  start= auto
sc.exe start sql_exporter
```

#### Verificar

```powershell
Invoke-WebRequest -Uri http://localhost:9375/metrics -UseBasicParsing | Select-Object -First 5
```

#### Linux (SQL Server no Linux)

```bash
SQL_EXP_VERSION="0.16.0"
wget https://github.com/burningalchemist/sql_exporter/releases/download/${SQL_EXP_VERSION}/sql_exporter-${SQL_EXP_VERSION}-linux-amd64.tar.gz
tar xzf sql_exporter-${SQL_EXP_VERSION}-linux-amd64.tar.gz
sudo mv sql_exporter-${SQL_EXP_VERSION}-linux-amd64/sql_exporter /usr/local/bin/
```

```bash
sudo tee /etc/systemd/system/sql_exporter.service << 'EOF'
[Unit]
Description=Prometheus SQL Exporter
After=network.target

[Service]
User=nobody
ExecStart=/usr/local/bin/sql_exporter --config.file=/etc/sql_exporter.yml
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now sql_exporter
```

#### Firewall (Windows)

```powershell
New-NetFirewallRule -DisplayName "sql_exporter" -Direction Inbound `
  -Protocol TCP -LocalPort 9375 -Action Allow
```

### Métricas coletadas

| Grupo | Prefixo |
|-------|---------|
| Windows MSSQL | `windows_mssql_*` |
| sql_exporter padrão | `mssql_*` |
| sql_exporter alternativo | `sqlserver_*` |

---

## Solução de problemas

**Verificar conectividade antes de adicionar ao gateway**

```bash
# Do servidor LGTM, confirme que a porta do exporter está acessível:
curl -s -o /dev/null -w "%{http_code}" http://<IP-DO-SERVIDOR>:<PORTA>/metrics
# Esperado: 200
```

**Gateway não coleta as métricas**

```bash
# Verificar erros no gateway
docker compose logs alloy-gateway | grep -i error

# Verificar se o arquivo foi carregado corretamente
docker compose logs alloy-gateway | grep -i "pull-legacy"
```

**Métricas não aparecem nos dashboards**

```bash
# Consultar diretamente no Mimir
docker exec grafana curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode 'query=up{instance="<instance>"}' | jq '.data.result'
```

**Atualizar targets sem reiniciar**

O Alloy Gateway detecta automaticamente alterações nos arquivos `conf.d/` e
recarrega a configuração. Basta salvar o arquivo e aguardar alguns segundos.
Para forçar o reload:

```bash
docker compose restart alloy-gateway
```
