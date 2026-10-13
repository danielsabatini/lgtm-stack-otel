# Gerenciamento e Provisionamento de Dashboards

> **Referência Técnica:** Este documento estabelece o fluxo oficial de edição, exportação e provisionamento automatizado de dashboards como código (*GitOps*) utilizando o schema de recursos nativos do Grafana 13 (`dashboard.grafana.app/v2`), detalhando as convenções de design, taxonomia de abas e a arquitetura completa da solução **MGC Internal DNS**.

> ✅ **Status (migração OpenTelemetry):** os dashboards consultam só os nomes da OTel Semantic Conventions. Push (agente) e pull (exporters convertidos no `otel-agent`) gravam o mesmo formato, então cada tipo de servidor tem **um único dashboard**, independente do método de coleta (seção 3).

---

## 1. Introdução

No Grafana, a edição visual de painéis pela interface web é ágil e intuitiva, mas sujeita à perda de alterações caso os containers sejam recriados ou atualizados. Por outro lado, manter os dashboards como arquivos JSON versionados no Git (*Dashboard-as-Code*) garante rastreabilidade, auditoria e recuperação instantânea.

A LGTM Stack adota *Dashboard-as-Code* com **fonte única da verdade nos geradores** de `artifacts/dashboards/`: scripts Python que montam cada dashboard a partir de módulos compartilhados (a linha de host, a linha de aplicações OBI, os padrões de painel) e gravam os JSONs em `grafana/provisioning/dashboards/`, de onde o Grafana os carrega. Assim, uma regra muda num lugar só e vale para todos os dashboards.

---

## 2. Objetivo

1. **Eliminar Duplicação de Arquivos:** Manter apenas uma pasta oficial de dashboards no repositório (`grafana/provisioning/dashboards/`).
2. **Preservar a Hierarquia de Tabs e Rows do Grafana 13:** Documentar o uso obrigatório da API nativa v2 (`dashboard.grafana.app/v2`) para que as abas (`TabsLayout`) nunca sejam desfeitas.
3. **Padronizar o Fluxo GitOps:** Toda mudança passa pelos geradores (`artifacts/dashboards/`) e é verificada contra a metodologia antes do commit.
4. **Documentar a Arquitetura da Solução DNS:** Especificar a decomposição em 3 camadas (*Linux, CoreDNS e etcd*) e os pilares de observabilidade do cluster DNS.

---

## 3. Estrutura Canônica de Diretórios

Cada tipo de servidor tem **um dashboard só**, que lista todos os hosts daquele tipo — com agente (push) ou coletados por pull. Isso é possível porque o pull é convertido no `otel-agent` para os mesmos nomes, atributos e semântica do agente (ver [METRICS.md](METRICS.md) §7.1): as consultas são as mesmas para os dois métodos. Cada servidor aparece **só no dashboard mais específico** para ele (onde a linha do host também está): com banco de dados → **Hosts + Database**; nó DNS → **DNS**; servidor da stack → **LGTM**. A variável `host` de Linux Hosts e Windows Hosts exclui esses servidores pelas métricas que os identificam (`mysql.uptime`, `postgresql.connection.max`, `sqlserver.user.connection.count`, `coredns_build_info`, `container.cpu.usage.total`), então nelas ficam só os servidores sem dashboard dedicado. Painéis cuja métrica não existe na origem do pull (ex.: logs, traces, load average no Windows) ficam sem dados para esses hosts.

```text
grafana/provisioning/dashboards/          ← JSONs gerados por artifacts/dashboards/ (não editar à mão)
├── Hosts/
│   ├── linux-hosts.json                  Linux Hosts (system.*, journald, OBI) — agente e node_exporter
│   └── windows-hosts.json                Windows Hosts (system.*, Event Log) — agente e windows_exporter
├── Hosts + Database/
│   ├── linux-mysql-hosts.json            Linux + MySQL (mysql.*) — agente e mysqld_exporter (ex.: DBaaS)
│   ├── linux-pgsql-hosts.json            Linux + PostgreSQL (postgresql.*) — agente e postgres_exporter (ex.: DBaaS)
│   └── windows-hosts-mssql.json          Windows + SQL Server (sqlserver.*) — agente e coletor mssql
├── DNS/
│   └── mgc-internal-dns.json             Linux (system.*) + CoreDNS + etcd (nomes dos exporters)
├── LGTM/
│   └── lgtm-stack.json                   Self-monitoring: pipeline OTel (otelcol_*), containers (container.*) e servidor da stack
└── dashboards.yaml                       Provider (recarga a cada 30 s)
```

---

## 4. Fluxo de Trabalho GitOps (Workflow)

```text
  [1. Alterar o gerador em artifacts/dashboards/]
                       │
                       ▼
  [2. python3 artifacts/dashboards/build.py]
      regenera os 7 JSONs + verifica a metodologia (saída não-zero se violar)
                       │
                       ▼
  [3. Conferir no Grafana (recarrega em até 30 s; recarregue a página)]
                       │
                       ▼
  [4. Git Commit + Push]
```

| Módulo | Papel |
|---|---|
| `lib.py` | Construtores de painéis (gauge, stat, timeseries, logs, traces), variáveis e o layout (linhas/abas, renderização condicional) no schema `dashboard.grafana.app/v2` |
| `hosts.py` | Linha de host Linux/Windows (5 pilares, modos single e multi-host), aba Logs, linha Aplicações (OBI) e a variável de host com exclusão dos servidores com dashboard dedicado |
| `linux_hosts.py`, `windows_hosts.py`, `linux_mysql.py`, `linux_pgsql.py`, `windows_mssql.py`, `lgtm_stack.py`, `dns.py` | Um gerador por dashboard (o `dns.py` regera a linha Linux e mantém as linhas CoreDNS/etcd do próprio arquivo) |
| `build.py` | Roda todos os geradores e o verificador `artifacts/scripts/check-dashboards-methodology.py` |

---

## 5. Edição pela UI (Protótipos)

A UI do Grafana é útil para **experimentar** um painel (consulta, visualização, layout). Uma mudança feita só na UI é **sobrescrita** na próxima execução do `build.py` e no próximo reload do provisioning: depois de validado, o painel deve ser levado ao gerador correspondente. Para inspecionar o JSON que a UI produziu:

```bash
curl -s -u admin:<senha> \
  "http://localhost:3000/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>" | jq '.spec.elements'
```

---

## 6. Como Incluir um Novo Dashboard

1. **Criar o gerador** em `artifacts/dashboards/<nome>.py`, reaproveitando `lib.Dash` e os módulos compartilhados (ex.: `hosts.host_tabs` para a linha de host, `hosts.app_row` para aplicações OBI). A pasta do arquivo de saída vira a pasta no Grafana (`foldersFromFilesStructure: true`).
2. **Registrar no `build.py`** (lista `TARGETS`: gerador → arquivo em `grafana/provisioning/dashboards/<Pasta>/<nome>.json`).
3. **Identidade:** `metadata.name` e `spec.uid` iguais, únicos na instância, em minúsculas com hífens — e nunca alterados depois de publicados (quebram favoritos, links e alertas).
4. **Registrar o UID** na tabela da seção 7.
5. **Rodar** `python3 artifacts/dashboards/build.py` e conferir no Grafana (`docker compose logs -f grafana | grep -i dashboard` mostra a importação).

## 7. UIDs Canônicos dos Dashboards

> ⚠️ **Nunca altere os UIDs** de dashboards já existentes. A alteração de UID quebra favoritos, links cruzados e alertas configurados.

| Dashboard | UID Canônico | Pasta | Coleta (push e pull) | Status |
|---|---|---|---|---|
| **Linux Hosts** | `linux-hosts` | `Hosts/` | agente; `node_exporter` | ✅ migrado |
| **Windows Hosts** | `windows-hosts` | `Hosts/` | agente; `windows_exporter` | ✅ migrado |
| **Linux + MySQL Hosts** | `linux-mysql-hosts` | `Hosts + Database/` | agente; `mysqld_exporter` (DBaaS) | ✅ migrado |
| **Linux + PostgreSQL Hosts** | `linux-pgsql-hosts` | `Hosts + Database/` | agente; `postgres_exporter` (DBaaS) | ✅ migrado |
| **Windows + SQL Server Hosts** | `windows-hosts-mssql` | `Hosts + Database/` | agente; coletor `mssql` do `windows_exporter` | ✅ migrado |
| **MGC Internal DNS** | `adth4vt` | `DNS/` | `node_exporter`, CoreDNS, etcd | ✅ migrado |
| **LGTM Stack Self-Monitoring** | `lgtm-stack` | `LGTM/` | telemetria interna dos coletores (`otelcol_*`), `docker_stats` e agente do servidor da stack | ✅ migrado |

---

## 8. Arquitetura da Solução MGC Internal DNS (`adth4vt`)

O dashboard **MGC Internal DNS** é uma visão de **cluster**: a variável `host` aceita vários nós e abre em **All**, com um valor ou uma linha por nó em todos os painéis (selecionar um nó vira um *zoom*). Ele monitora a infraestrutura de resolução de nomes interna em 3 camadas interdependentes, organizadas em linhas colapsáveis (*Rows*) e abas metodológicas (*Tabs*):

```text
MGC Internal DNS (adth4vt)
├── 1. Linha Linux (Sistema Operacional dos Servidores DNS — system.*, mesmas abas do Linux Hosts em modo multi-host)
│   ├── Health: CPU, Memória, Filesystem e Rede em percentual normalizado.
│   ├── Capacity: Load x CPUs, Memória, Swap, Filesystem e Inodes por ponto de montagem.
│   ├── Activity: Throughput e IOPS de Disco e Tráfego de Rede.
│   ├── Diagnostics: CPU por estado, Disco ocupado, Latência de Disco e Erros/Descartes de Rede.
│   └── Inventory: Uptime, CPUs, RAM, Swap, Filesystem e SO (target_info).
│
├── 2. Linha CoreDNS (Camada de Resolução DNS)
│   ├── Health: Status UP/DOWN, DNS Error Rate (%), Query Rate (req/s), Upstream Health (%), Latência Interna p99 e Latência Forward p99.
│   ├── Capacity: Cache Entries (Total em Cache vs Capacidade Combinada de 110 K), File Descriptors (alocados vs limite) e Memória RSS do processo.
│   ├── Activity: Total de Requisições, Requisições por Zona (local/recursiva), Respostas por Rcode (NOERROR, NXDOMAIN, SERVFAIL) e Throughput de Cache (Hits vs Misses).
│   ├── Diagnostics: Panics, Reload Failures, Rejeições de Concorrência Upstream, Erros por Zona, Latência p99 por Zona, Cache - Valid Entries (Success - teto 50 K), Cache - Denial Entries (NXDOMAIN - teto 5 K), Taxa de Hit do Cache (%) e Evicções de Cache (/s).
│   └── Inventory: Uptime, Plugins Habilitados, Versão do Binário, Revisão Git, Versão do compilador Go e Teto Máximo de FDs.
│
└── 3. Linha etcd (Camada de Armazenamento e Consenso do Cluster DNS)
    ├── Health: Status UP/DOWN do membro, Cluster Role (Leader/Follower), Cluster Quorum e Taxa de Falhas em Propostas Raft.
    ├── Capacity: Tamanho da base de dados bbolt comparada com a cota (quota) e Total de Chaves/Registros DNS mantidos.
    ├── Activity: Volume de Propostas Raft (Committed vs Failed) e Histórico de Trocas de Liderança (/s).
    ├── Diagnostics: Latência de Disco WAL Fsync p99 (causa raiz de perda de quorum), Backend Commit p99 e RTT de Rede entre Pares (Peer RTT p99).
    └── Inventory: Uptime do membro, Cota de Backend configurada, Versão do etcd e Versão do Cluster.
```

---

## 9. Padrões Obrigatórios de Design dos Painéis

### 9.1 Padrão de Legendas e Renderização de Metadados:

* **Dashboards Multi-Node (ex: MGC Internal DNS `adth4vt`):**
  * **Métricas com Múltiplas Instâncias:** Utilizam o separador pipe ` | ` na legenda: `{{host.name}} | {{version}}` ou `{{host.name}} | {{device}}` (identidade do host pelo `host.name`, ver [METRICS.md](METRICS.md) §5).
  * **Painéis Stat de Metadados:** Configurados com `textMode: "name"`, `justifyMode: "center"`, cor de fundo `colorMode: "none"` e tamanho fixo `text.valueSize: 16`.

* **Dashboards Single-Node (ex: Linux Hosts `linux-hosts`):**
  * **Cards Stat Numéricos (Uptime, Cores, Memória, Swap, Disco):** Configurados com `textMode: "value"`, `justifyMode: "center"`, `colorMode: "none"` e `legendFormat: ""`. O valor é renderizado limpo e centralizado no centro do card.
  * **Cards Stat de Texto (OS / Versão):** Configurados com `textMode: "name"`, `justifyMode: "center"`, `text.valueSize: 16` e `legendFormat: "{{pretty_name}}"`.

### 9.2 Padrão de Layout para Gráficos de Séries Temporais (Timeseries):
* **1 Coluna Obrigatória (`maxColumnCount: 1`):** Gráficos do tipo `Time series` devem ocupar a **largura total (1 coluna / 24 colunas de grid)** para proporcionar resolução horizontal máxima na análise de tendências temporais, sazonalidade e picos de tráfego.

### 9.3 Padrão de Layout para Abas de Cards Stat (Health e Inventory):
* **Configuração Canônica do Grid:**
  * **Multi-Node:** `columnWidthMode: "Narrow"`, `rowHeightMode: "Short"`, `maxColumnCount: 2` (grade simétrica de 2 colunas).
  * **Single-Node:** `columnWidthMode: "Narrow"`, `rowHeightMode: "Short"`, `maxColumnCount: 4` ou `3` (distribuição horizontal compacta).

### 9.4 Padrão para Abas com Tipos Heterogêneos / Misturados (Stat + Timeseries):
* **1 Coluna Obrigatória (`maxColumnCount: 1`):** Quando uma aba combina cards `Stat` e gráficos `Time series` na mesma aba (ex: Diagnostics). Impede que gráficos de linha fiquem comprimidos ao lado de cards de resumo.

### 9.5 Padrão de Descrições em 3 Blocos (Tooltips):
Todo painel deve seguir estritamente o padrão em 3 blocos definido em [METRICS.md](METRICS.md):
1. **O que é:** Definição simples e contextualizada em linguagem acessível.
2. **• O que observar:** Padrão esperado, limites normais e thresholds de alerta.
3. **• Ação em caso de problema:** Comandos objetivos de terminal (`journalctl`, `systemctl`, `dig`, `etcdctl`) para diagnóstico e resolução rápida.

---

### 9.6 Conformidade com a Metodologia

Os dashboards seguem [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md), verificado por `artifacts/scripts/check-dashboards-methodology.py` (executado automaticamente pelo `artifacts/dashboards/build.py`):

* **Health:** só `%`, status UP/DOWN ou latência p99 de serviço, com os limiares (os limiares e cores de alarme vivem **apenas** no Health). Nos bancos: MySQL Status + Slow Queries (%); PostgreSQL Uso de Conexões (%) + Rollback (%); SQL Server Uso do Log de Transações (máx. %).
* **Capacity:** unidades absolutas — usado × total (linha tracejada "Limite"), ex.: filesystem em bytes e inodes em contagem por mountpoint.
* **Activity:** taxas (`/s`) sem limiares; **Diagnostics:** decomposição e causa raiz (cache hit, latência de disco, por rota, erros por tipo), sem limiares; **Inventory:** totais, versões, uptime.
* **Aplicações (OBI)** é uma linha própria (Linux Hosts, Linux + MySQL e Linux + PostgreSQL) com os pilares do método RED: Health (taxa de erros % e latência **p99** por serviço), Activity (req/s), Diagnostics (por rota) e Traces. Ela só aparece para hosts com aplicações instrumentadas pelo OBI que tenham dados **em qualquer ponto do período selecionado** (renderização condicional por uma variável oculta com `last_over_time(...[$__range])`, recalculada ao trocar host ou período; §9.2 — sem compartimentos vazios).
* **Logs:** abas Security, System e Application (categorias da metodologia); Erros de Negócio não tem fonte e é omitida (§9.2).

### 9.7 Padrão de Consultas (OpenTelemetry no Mimir):
* **Nomes UTF-8 entre aspas:** métricas e atributos com ponto vão dentro do seletor: `{"system.cpu.time", "host.name"="$host", state="idle"}`; em agregações, `sum by ("service.name") (...)`. Na legenda, `{{host.name}}` funciona normalmente.
* **Variável de host:** `query_result(count by ("host.name") ({"system.uptime", "os.type"="linux"}) unless on ("host.name") count by ("host.name") ({"mysql.uptime"}) unless …)` com regex `/host\.name="([^"]+)"/` (o `os.type` separa Linux e Windows, que usam os mesmos nomes `system.*`).
* **Deduplicação:** envolva gauges em `max by (<dimensões reais>)` e taxas em `max by (<dimensões>) (rate(...))` antes de somar. Um upgrade do Collector muda `otel_scope_version` e, por ~5 min, a série antiga e a nova coexistem — sem o `max by`, os valores dobram.
* **Intervalo de taxa:** o datasource Mimir declara `timeInterval: 60s` (maior intervalo de coleta da stack: receivers de banco e parte dos pulls). Assim `$__rate_interval` ≥ 4 min e todo `rate()` tem amostras suficientes — não fixe janelas como `[1m]`.
* **Filtros de banco:** variáveis multi-seleção (padrão *All*) abaixo do Host — **Instância** no SQL Server (`"sqlserver.instance.name"=~"$instance"`, label promovido no Mimir; no Event Log, `windows_eventlog_provider=~"(MSSQL\\$)?(${instance:regex})"`) e **Banco** no PostgreSQL (`"db.namespace"=~"$database"`; no log, `| db_namespace=~"${database:regex}" or db_namespace=""` para manter as mensagens do servidor). Métricas do servidor inteiro (ex.: `postgresql.connection.max`, checkpoints) não são filtradas. O MySQL não tem filtro de banco: o receiver e o `mysqld_exporter` só entregam métricas do servidor (`SHOW GLOBAL STATUS`); as por tabela/índice ficam desligadas pela Política Lean.
* **Histogramas nativos (OBI):** taxa com `histogram_count(rate(...))`, percentil com `histogram_quantile(0.95, sum by (...) (rate(...)))` e `exemplar: true` para abrir o trace pelo `trace_id`.
* **Logs:** `{host_name="$host"} | category="security"` (`category` é structured metadata, ver [LOGS.md](LOGS.md) §3).
* **Traces:** `{ resource.host.name = "$host" }`.

---

## 10. Diagnóstico de Erros Comuns

### 10.1 Erro: Tabs virando linhas simples (TabsLayout destruído via API)
* **Causa:** Utilizar o endpoint legado da API v1 (`POST /api/dashboards/db`) para salvar ou atualizar dashboards no Grafana 13. Esse endpoint antigo achata todas as tabs internas em linhas simples (*flat rows*).
* **Solução:** Utilize sempre o endpoint nativo de recursos v2 do Grafana 13:
  * **Leitura:** `GET /apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>`
  * **Escrita:** `PUT /apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>`

### 10.2 Dashboard Duplicado na UI
* **Causa:** O arquivo de provisioning possui `metadata.name` ou `uid` diferente do que foi salvo no banco SQLite do Grafana.
* **Solução:** Exclua o dashboard duplicado pela UI e recarregue o Grafana para que o provisioning recrie com o UID canônico correto.

---

## 11. Governança e Referências

* Para a taxonomia de abas e categorização de métricas, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para o padrão obrigatório de descrições e tooltips dos painéis, consulte [METRICS.md](METRICS.md).
* Para fronteiras de rede e topologia de coleta (OTel Gateway e agentes), consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](../README.md)
