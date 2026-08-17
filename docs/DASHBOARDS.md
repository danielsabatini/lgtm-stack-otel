# Gerenciamento e Provisionamento de Dashboards

> **Referência Técnica:** Este documento estabelece o fluxo oficial de edição, exportação e provisionamento automatizado de dashboards como código (*GitOps*) utilizando o schema de recursos nativos do Grafana 13 (`dashboard.grafana.app/v2`), detalhando as convenções de design, taxonomia de abas e a arquitetura completa da solução **MGC Internal DNS**.

---

## 1. Introdução

No Grafana, a edição visual de painéis pela interface web é ágil e intuitiva, mas sujeita à perda de alterações caso os containers sejam recriados ou atualizados. Por outro lado, manter os dashboards como arquivos JSON versionados no Git (*Dashboard-as-Code*) garante rastreabilidade, auditoria e recuperação instantânea.

A LGTM Stack adota um modelo de **Fonte Única da Verdade (Single Source of Truth)** onde todos os dashboards são armazenados exclusivamente na pasta canônica de provisioning `grafana/provisioning/dashboards/`.

---

## 2. Objetivo

1. **Eliminar Duplicação de Arquivos:** Manter apenas uma pasta oficial de dashboards no repositório (`grafana/provisioning/dashboards/`).
2. **Preservar a Hierarquia de Tabs e Rows do Grafana 13:** Documentar o uso obrigatório da API nativa v2 (`dashboard.grafana.app/v2`) para que as abas (`TabsLayout`) nunca sejam desfeitas.
3. **Padronizar o Fluxo GitOps:** Fornecer os comandos simples para exportar alterações da UI diretamente para o arquivo versionado no Git.
4. **Documentar a Arquitetura da Solução DNS:** Especificar a decomposição em 3 camadas (*Linux, CoreDNS e etcd*) e os pilares de observabilidade do cluster DNS.

---

## 3. Estrutura Canônica de Diretórios

Todos os arquivos JSON de dashboards residem sob a árvore de provisioning do Grafana:

```text
lgtm-stack/
└── grafana/provisioning/dashboards/    ← Fonte Única da Verdade dos Dashboards
    ├── Hosts/
    │   ├── linux-hosts.json            (Linux Hosts - UID: linux-hosts | Single-Node)
    │   └── windows-hosts.json          (Windows Hosts - UID: windows-hosts | Single-Node)
    ├── Hosts + Database/
    │   ├── linux-mysql-hosts.json      (Linux + MySQL - UID: linux-mysql-hosts)
    │   ├── linux-pgsql-hosts.json      (Linux + PostgreSQL - UID: linux-pgsql-hosts)
    │   └── windows-hosts-mssql.json    (Windows + SQL Server - UID: windows-hosts-mssql)
    ├── DNS/
│   │   └── mgc-internal-dns.json       (MGC Internal DNS - UID: adth4vt | Multi-Node Cluster)
    ├── LGTM/
    │   └── lgtm-stack.json             (LGTM Self-Monitoring - UID: lgtm-stack)
    └── dashboards.yaml                 (Configuração de Hot-Reload a cada 10s)
```

---

## 4. Fluxo de Trabalho GitOps (Workflow)

```text
  [1. Edição e Ajuste Visual na UI do Grafana]
                       │
                       ▼
  [2. Exportar Diretamente via API v2 Nativa para o Arquivo de Provisioning]
  (curl -u admin:senha "http://localhost:3000/apis/dashboard.grafana.app/v2/...")
                       │
                       ▼
  [3. Salvar o JSON em grafana/provisioning/dashboards/<Pasta>/<nome>.json]
                       │
                       ▼
  [4. Git Commit + Push (O Grafana hot-recarrega as mudanças em até 10s)]
```

---

## 5. Como Exportar e Persistir Alterações da UI

Com o Grafana 13, não é necessário fazer conversões manuais de JSON. Basta realizar uma chamada `GET` na API nativa v2 para obter o arquivo pronto no formato de provisioning:

```bash
# Exemplo para salvar o dashboard MGC Internal DNS (UID: adth4vt):
curl -s -u admin:changeme \
  "http://localhost:3000/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/adth4vt" \
  | jq . > grafana/provisioning/dashboards/DNS/mgc-internal-dns.json

# Exemplo para salvar o dashboard Linux Hosts (UID: linux-hosts):
curl -s -u admin:changeme \
  "http://localhost:3000/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/linux-hosts" \
  | jq . > grafana/provisioning/dashboards/Hosts/linux-hosts.json
```

---

## 6. Como Incluir um Novo Dashboard Manualmente (Guia Passo a Passo)

Para adicionar um novo dashboard à stack de forma que ele seja carregado automaticamente pelo Grafana e versionado no Git, siga o procedimento abaixo:

### Passo 1: Definir a Pasta e Nome do Arquivo
Crie o arquivo JSON dentro de `grafana/provisioning/dashboards/<Categoria>/<nome-do-dashboard>.json`.
* A pasta onde o arquivo for colocado virará automaticamente uma pasta organizada no menu do Grafana (graças ao parâmetro `foldersFromFilesStructure: true` no `dashboards.yaml`).
* **Exemplos de Pastas:** `Hosts/`, `DNS/`, `Hosts + Database/`, `Applications/`.

```bash
# Exemplo: criar uma nova pasta para microsserviços
mkdir -p grafana/provisioning/dashboards/Applications
```

### Passo 2: Estruturar o JSON com o Envelope Kubernetes v2
Todo novo dashboard **deve obrigatoriamente** conter o envelope de recurso nativo do Grafana 13 (`dashboard.grafana.app/v2`):

```json
{
  "apiVersion": "dashboard.grafana.app/v2",
  "kind": "Dashboard",
  "metadata": {
    "name": "meu-novo-dashboard"
  },
  "spec": {
    "uid": "meu-novo-dashboard",
    "title": "Meu Novo Dashboard",
    "schemaVersion": 41,
    "timezone": "browser",
    "editable": true,
    "tags": ["meu-servico", "producao"],
    "layout": {
      "kind": "RowsLayout",
      "spec": {
        "rows": []
      }
    },
    "elements": {}
  }
}
```

> ⚠️ **Regras Críticas de Identidade:**
> 1. `metadata.name` e `spec.uid` **devem ter exatamente o mesmo valor** (ex: `meu-novo-dashboard`).
> 2. O `uid` deve ser único em toda a instância do Grafana (use apenas letras minúsculas e hifens).
> 3. Nunca altere o `uid` após colocar o dashboard em produção.

### Passo 3: Registrar o UID na Tabela de Governança
Adicione o novo dashboard na tabela de UIDs Canônicos (Seção 7 deste documento) para evitar colisões e manter o catálogo atualizado.

### Passo 4: Validação do Hot-Reload Automático (Sem Reiniciar)
O Grafana verifica a pasta `grafana/provisioning/dashboards/` **a cada 10 segundos**.

1. Salve o arquivo JSON na pasta.
2. Acompanhe os logs do Grafana para confirmar a detecção e importação:
   ```bash
   docker compose logs -f grafana | grep -i "dashboard"
   ```
3. Abra a interface web do Grafana (`http://localhost:3000/dashboards`) e confirme que o dashboard apareceu na pasta correspondente.

---

## 7. UIDs Canônicos dos Dashboards

> ⚠️ **Nunca altere os UIDs** de dashboards já existentes. A alteração de UID quebra favoritos, links cruzados e alertas configurados.

| Dashboard | UID Canônico | Pasta no Provisioning | Escopo | Componentes / Tags |
|---|---|---|---|---|
| **MGC Internal DNS** | `adth4vt` | `DNS/` | Multi-Node (Cluster) | `linux`, `coredns`, `etcd`, `dns` |
| **Linux Hosts** | `linux-hosts` | `Hosts/` | Single-Node | `linux`, `node-exporter`, `infrastructure` |
| **Windows Hosts** | `windows-hosts` | `Hosts/` | Single-Node | `windows`, `windows-exporter`, `infrastructure` |
| **Linux + MySQL Hosts** | `linux-mysql-hosts` | `Hosts + Database/` | Multi-Node | `linux`, `mysql`, `database` |
| **Linux + PostgreSQL Hosts** | `linux-pgsql-hosts` | `Hosts + Database/` | Multi-Node | `linux`, `postgres`, `database` |
| **Windows + MSSQL Hosts** | `windows-hosts-mssql` | `Hosts + Database/` | Multi-Node | `windows`, `mssql`, `database` |
| **LGTM Stack Self-Monitoring** | `lgtm-stack` | `LGTM/` | Stack Local | `lgtm`, `mimir`, `loki`, `tempo`, `alloy` |

---

## 8. Arquitetura da Solução MGC Internal DNS (`adth4vt`)

O dashboard **MGC Internal DNS** monitora a infraestrutura de resolução de nomes interna em 3 camadas interdependentes, organizadas em linhas colapsáveis (*Rows*) e abas metodológicas (*Tabs*):

```text
MGC Internal DNS (adth4vt)
├── 1. Linha Linux (Sistema Operacional dos Servidores DNS)
│   ├── Health: Sinais vitais de CPU, Memória, Disco e Rede em percentual normalizado.
│   ├── Capacity: Composição e limites de CPU Load, Memória RAM, Swap, FS Root e Inodes.
│   ├── Activity: Volume temporal de Throughput e IOPS de Disco e Tráfego de Rede.
│   ├── Diagnostics: Análise de causa raiz com Modos de CPU, PSI (CPU/Mem/IO), Latência de Disco e Erros/Drops de Rede.
│   ├── Inventory: Uptime, Total de Cores, RAM Total, Swap Total, FS Total e Versão do OS.
│   └── Logs: Coleta estruturada de Security (SSH), System (systemd/kernel/cron), Application e Platform.
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
  * **Métricas com Múltiplas Instâncias:** Utilizam o separador pipe ` | ` na legenda: `{{instance}} | {{version}}`, `{{instance}} | {{job}}` ou `{{instance}} | {{device}}`.
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
* Para fronteiras de rede e topologia de coleta do Alloy Gateway, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](../README.md)
