# Gerenciamento e Provisionamento de Dashboards

> **Referência Técnica:** Este documento estabelece o fluxo de edição, backup, conversão para o schema Kubernetes do Grafana 13 (`dashboard.grafana.app/v2`) e provisionamento automatizado de dashboards como código (GitOps).

---

## 1. Introdução

No Grafana, a edição visual de painéis pela interface web é ágil, mas sujeita à perda de alterações caso os containers sejam recriados ou atualizados. Por outro lado, manter dashboards como código (*Dashboard-as-Code*) garante versionamento no Git, auditoria e recuperação instantânea.

Este repositório adota um fluxo de trabalho estruturado que une a flexibilidade da edição visual na UI com a segurança do provisionamento automatizado como código.

---

## 2. Objetivo

1. **Evitar Perda de Customizações:** Garantir que qualquer dashboard criado ou editado na UI seja versionado e persistido no Git.
2. **Explicar a Conversão do Grafana 13:** Fornecer o script e as regras de transformação para o novo schema de recursos v2 do Grafana 13.
3. **Prevenir Regressões Visuais:** Documentar as chamadas de API corretas que preservam a hierarquia de `TabsLayout` e `RowsLayout`.

---

## 3. Estrutura de Diretórios (Backup vs. Provisioning)

Os arquivos JSON dos dashboards residem em duas pastas complementares com papéis distintos:

```text
lgtm-stack/
├── grafana-dashboards-backup/          ← Cópias exportadas da UI do Grafana (sem envelope)
│   ├── Hosts/
│   │   ├── linux-hosts.json
│   │   └── windows-hosts.json
│   ├── Hosts + Database/
│   │   ├── linux-mysql-hosts.json
│   │   ├── linux-pgsql-hosts.json
│   │   └── windows-mssql-hosts.json
│   └── DNS/
│       └── mgc-internal-dns-solution.json
│
└── grafana/provisioning/dashboards/    ← Formato de Provisioning (carregado automaticamente)
    ├── Hosts/
    │   ├── linux-hosts.json
    │   └── windows-hosts.json
    ├── Hosts + Database/
    │   ├── linux-mysql-hosts.json
    │   ├── linux-pgsql-hosts.json
    │   └── windows-hosts-mssql.json
    └── DNS/
        └── mgc-internal-dns-solution.json
```

> ⚠️ **Regra de Ouro:** Nunca edite manualmente os arquivos dentro de `grafana/provisioning/dashboards/`. O fluxo correto é editar no Grafana, salvar o backup e converter para o formato de provisioning.

---

## 4. Fluxo de Trabalho (Workflow)

```text
  [1. Edição visual no Grafana UI]
                 │
                 ▼
  [2. Exportar JSON do Dashboard (Share → Export)]
                 │
                 ▼
  [3. Salvar em grafana-dashboards-backup/<Pasta>/]
                 │
                 ▼
  [4. Converter para o Envelope Kubernetes v2]
                 │
                 ▼
  [5. Salvar em grafana/provisioning/dashboards/<Pasta>/]
                 │
                 ▼
  [6. Git Commit + Push (Grafana hot-recarrega em até 10s)]
```

---

## 5. Conversão: Export da UI → Formato de Provisioning (Grafana 13)

### 5.1 A Diferença entre os Formatos
* **Formato Exportado pela UI (Backup em `grafana-dashboards-backup/`):** JSON simples sem o envelope de metadados e sem o campo `uid` para evitar conflitos de importação manual.
* **Formato de Provisioning (em `grafana/provisioning/dashboards/`):** JSON envolvido com o schema de recursos Kubernetes `dashboard.grafana.app/v2`, com `metadata.name` e `spec.uid` canônicos obrigatórios.

### 5.2 Script de Conversão Automática (Python)
Execute o script abaixo para transformar o backup no arquivo de provisioning:

```python
#!/usr/bin/env python3
"""
Converte um dashboard exportado da UI do Grafana 13 para o formato de provisioning.

Uso:
    python3 convert-dashboard.py <backup.json> <output-provisioning.json> <uid>
"""
import json, sys

def convert(backup_path, output_path, uid):
    with open(backup_path, 'r', encoding='utf-8') as f:
        content = json.load(f)

    # Injeta o UID canônico dentro do spec
    content['uid'] = uid

    # Cria o envelope de recurso v2
    provisioning = {
        "apiVersion": "dashboard.grafana.app/v2",
        "kind": "Dashboard",
        "metadata": {
            "name": uid
        },
        "spec": content
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(provisioning, f, indent=2, ensure_ascii=False)

    print(f"✅ Gerado com sucesso: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: convert-dashboard.py <backup.json> <output.json> <uid>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
```

---

## 6. UIDs Canônicos dos Dashboards

> ⚠️ **Nunca altere os UIDs** de dashboards já existentes. A alteração de UID quebra favoritos, links cruzados e alertas configurados.

| Dashboard | UID Canônico | Pasta no Provisioning |
|---|---|---|
| **Linux Hosts** | `linux-hosts` | `Hosts/` |
| **Windows Hosts** | `windows-hosts` | `Hosts/` |
| **Linux + MySQL Hosts** | `linux-mysql-hosts` | `Hosts + Database/` |
| **Linux + PostgreSQL Hosts** | `linux-pgsql-hosts` | `Hosts + Database/` |
| **Windows + MSSQL Hosts** | `windows-hosts-mssql` | `Hosts + Database/` |
| **MGC Internal DNS Solution** | `adth4vt` | `DNS/` |
| **LGTM Stack Self-Monitoring** | `lgtm-stack` | `LGTM/` |

---

## 7. Como o Provisioning Funciona (Hot-Reload)

O arquivo `grafana/provisioning/dashboards/dashboards.yaml` controla o carregamento automático dos painéis:
* **`foldersFromFilesStructure: true`:** As subpastas (`Hosts/`, `DNS/`, `Hosts + Database/`) são criadas automaticamente como pastas organizadas no Grafana.
* **`updateIntervalSeconds: 10`:** O Grafana detecta modificações nos arquivos de provisioning a cada 10 segundos e aplica o *hot-reload* automaticamente sem necessidade de reiniciar o container.

---

## 8. Padrão de Design para Painéis de Inventário e Versão

Para métricas informativas de metadados (como `*_build_info`, `*_os_info` ou `*_version`) que retornam o valor numérico constante `1` e carregam os dados em labels de texto, adota-se o seguinte padrão oficial de design no Grafana:

### 8.1 Configuração Canônica do Painel Stat:
* **Tipo de Painel:** `Stat`
* **Formato da Legenda:** `{{instance}} > {{label_do_dado}}` (ex: `{{instance}} > {{version}}` ou `{{instance}} > {{server_version}}`).
* **Modo de Texto (`textMode`):** `name` (renderiza o texto da legenda formatado).
* **Tamanho Fixo da Fonte (`text.valueSize`):** **`16`** (16px) — *evita distorções de escala automática e garante alinhamento simétrico entre as colunas*.
* **Alinhamento (`justifyMode`):** `center`.
* **Cor de Fundo (`colorMode`):** `none` (fundo neutro limpo).

### 8.2 Exemplo de Renderização Visual:
```text
┌───────────────────────────────┬───────────────────────────────┬───────────────────────────────┐
│     dns-ne1-1 > 1.14.6        │      dns-ne1-2 > 1.14.6       │      dns-ne1-3 > 1.14.6       │
└───────────────────────────────┴───────────────────────────────┴───────────────────────────────┘
```

### 8.3 Padrão de Layout para Gráficos de Séries Temporais (Timeseries):
* **1 Coluna Obrigatória (`maxColumnCount: 1`):** Gráficos do tipo `Time series` devem ser configurados sempre ocupando a **largura total (1 coluna / 24 colunas de grid)**.
* **Motivo:** Gráficos de linha empilhados em 2 ou 3 colunas espremem o eixo horizontal de tempo e dificultam a visualização de picos, anomalias e correlação de tendências. A largura total proporciona máxima resolução horizontal de diagnóstico.

### 8.4 Padrão de Layout para Abas de Cards Stat (Health e Inventory):
* **Configuração Canônica do Grid:**
  * **Largura Mínima de Coluna (`columnWidthMode`):** `Narrow`
  * **Altura da Linha (`rowHeightMode`):** `Short`
  * **Máximo de Colunas (`maxColumnCount`):** `2`
* **Motivo:** Mantém os cards de sinais vitais e inventário compactos, simétricos e organizados em uma grade de 2 colunas, evitando rolagem vertical desnecessária e permitindo que toda a visão caiba no topo da tela.

### 8.5 Padrão para Abas com Tipos Heterogêneos / Misturados (Stat + Timeseries):
* **1 Coluna Obrigatória (`maxColumnCount: 1`):** Quando uma aba combina diferentes tipos de visualização (ex: cards `Stat` de alarmes e gráficos `Time series` de diagnóstico na mesma aba).
* **Motivo:** Impede o desalinhamento estético de renderizar um card Stat ao lado de um gráfico de linha espremido, garantindo que cada elemento tenha sua largura completa preservada.

---

## 9. Diagnóstico de Erros Comuns

### 9.1 Erro: Tabs virando linhas simples (TabsLayout destruído via API)
* **Causa:** Utilizar o endpoint legado da API v1 (`POST /api/dashboards/db`) para salvar ou atualizar dashboards no Grafana 13. Esse endpoint antigo achata todas as tabs internas em linhas simples (*flat rows*).
* **Solução:** Utilize sempre o endpoint nativo de recursos v2 do Grafana 13:
  * **Leitura:** `GET /apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>`
  * **Escrita:** `PUT /apis/dashboard.grafana.app/v2/namespaces/default/dashboards/<uid>`

### 9.2 Dashboard Duplicado na UI
* **Causa:** O arquivo de provisioning possui `metadata.name` ou `uid` diferente do que foi salvo no banco SQLite do Grafana.
* **Solução:** Exclua o dashboard duplicado pela UI e recarregue o Grafana para que o provisioning recrie com o UID canônico correto.

---

## 10. Governança e Referências

* Para a taxonomia de abas e categorização de métricas, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para o padrão obrigatório de descrições e tooltips dos painéis, consulte [METRICS.md](METRICS.md).

---
🔙 Voltar: [README Principal](../README.md)
