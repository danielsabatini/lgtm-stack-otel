# Gerenciamento e Provisionamento de Dashboards

> **Referência Técnica:** Este documento estabelece o fluxo oficial de edição, exportação e provisionamento automatizado de dashboards como código (*GitOps*) utilizando o schema de recursos nativos do Grafana 13 (`dashboard.grafana.app/v2`).

---

## 1. Introdução

No Grafana, a edição visual de painéis pela interface web é ágil e intuitiva, mas sujeita à perda de alterações caso os containers sejam recriados ou atualizados. Por outro lado, manter os dashboards como arquivos JSON versionados no Git (*Dashboard-as-Code*) garante rastreabilidade, auditoria e recuperação instantânea.

A LGTM Stack adota um modelo de **Fonte Única da Verdade (Single Source of Truth)** onde todos os dashboards são armazenados exclusivamente na pasta canônica de provisioning `grafana/provisioning/dashboards/`.

---

## 2. Objetivo

1. **Eliminar Duplicação de Arquivos:** Manter apenas uma pasta oficial de dashboards no repositório (`grafana/provisioning/dashboards/`).
2. **Preservar a Hierarquia de Tabs e Rows do Grafana 13:** Documentar o uso obrigatório da API nativa v2 (`dashboard.grafana.app/v2`) para que as abas (`TabsLayout`) nunca sejam desfeitas.
3. **Padronizar o Fluxo GitOps:** Fornecer os comandos simples para exportar alterações da UI diretamente para o arquivo versionado no Git.

---

## 3. Estrutura Canônica de Diretórios

Todos os arquivos JSON de dashboards residem sob a árvore de provisioning do Grafana:

```text
lgtm-stack/
└── grafana/provisioning/dashboards/    ← Fonte Única da Verdade dos Dashboards
    ├── Hosts/
    │   ├── linux-hosts.json            (Linux Hosts - UID: linux-hosts)
    │   └── windows-hosts.json          (Windows Hosts - UID: windows-hosts)
    ├── Hosts + Database/
    │   ├── linux-mysql-hosts.json      (Linux + MySQL - UID: linux-mysql-hosts)
    │   ├── linux-pgsql-hosts.json      (Linux + PostgreSQL - UID: linux-pgsql-hosts)
    │   └── windows-hosts-mssql.json    (Windows + SQL Server - UID: windows-hosts-mssql)
    ├── DNS/
    │   └── mgc-internal-dns-solution.json (MGC Internal DNS - UID: adth4vt)
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
  | jq . > grafana/provisioning/dashboards/DNS/mgc-internal-dns-solution.json
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

| Dashboard | UID Canônico | Pasta no Provisioning |
|---|---|---|
| **Linux Hosts** | `linux-hosts` | `Hosts/` |
| **Windows Hosts** | `windows-hosts` | `Hosts/` |
| **Linux + MySQL Hosts** | `linux-mysql-hosts` | `Hosts + Database/` |
| **Linux + PostgreSQL Hosts** | `linux-pgsql-hosts` | `Hosts + Database/` |
| **Windows + MSSQL Hosts** | `windows-hosts-mssql` | `Hosts + Database/` |
| **MGC Internal DNS** | `adth4vt` | `DNS/` |
| **LGTM Stack Self-Monitoring** | `lgtm-stack` | `LGTM/` |

---

## 8. Como o Provisioning Funciona (Hot-Reload)

O arquivo `grafana/provisioning/dashboards/dashboards.yaml` controla o carregamento automático dos painéis:
* **`foldersFromFilesStructure: true`:** As subpastas (`Hosts/`, `DNS/`, `Hosts + Database/`) são criadas automaticamente como pastas organizadas no Grafana.
* **`updateIntervalSeconds: 10`:** O Grafana detecta modificações nos arquivos de provisioning a cada 10 segundos e aplica o *hot-reload* automaticamente sem necessidade de reiniciar o container.

---

## 9. Padrões Obrigatórios de Design dos Painéis

### 9.1 Padrão para Métricas de Inventário e Versão (Metadados em Labels):
Para métricas como `*_build_info`, `*_os_info` ou `*_version` (onde o valor numérico é constante `1` e o dado está no label):
* **Tipo:** `Stat`
* **Formato da Legenda:** `{{instance}} > {{label_do_dado}}` (ex: `{{instance}} > {{version}}`).
* **Modo de Texto (`textMode`):** `name`.
* **Tamanho Fixo da Fonte (`text.valueSize`):** **`16`** (16px) — *mantém alinhamento simétrico sem distorção*.
* **Alinhamento (`justifyMode`):** `center`.
* **Cor de Fundo (`colorMode`):** `none`.

### 9.2 Padrão de Layout para Gráficos de Séries Temporais (Timeseries):
* **1 Coluna Obrigatória (`maxColumnCount: 1`):** Gráficos do tipo `Time series` devem ocupar a **largura total (1 coluna / 24 colunas de grid)** para proporcionar resolução horizontal máxima na análise de tendências temporais e picos.

### 9.3 Padrão de Layout para Abas de Cards Stat (Health e Inventory):
* **Configuração Canônica do Grid:**
  * **Largura Mínima de Coluna (`columnWidthMode`):** `Narrow`
  * **Altura da Linha (`rowHeightMode`):** `Short`
  * **Máximo de Colunas (`maxColumnCount`):** `2`
* **Motivo:** Mantém os cards compactos, simétricos e organizados em uma grade de 2 colunas, evitando rolagem vertical desnecessária.

### 9.4 Padrão para Abas com Tipos Heterogêneos / Misturados (Stat + Timeseries):
* **1 Coluna Obrigatória (`maxColumnCount: 1`):** Quando uma aba combina cards `Stat` e gráficos `Time series` na mesma aba (ex: Diagnostics).
* **Motivo:** Impede o desalinhamento estético de renderizar um card Stat ao lado de um gráfico de linha comprimido.

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

---
🔙 Voltar: [README Principal](../README.md)
