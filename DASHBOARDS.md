# Gerenciamento de Dashboards

Este documento descreve o fluxo completo de trabalho com dashboards na stack LGTM, desde a edição no Grafana até o versionamento e o carregamento automático via provisioning.

---

## Estrutura de Arquivos

```
lgtm-stack/
├── grafana-dashboards-backup/          # ← Cópias exportadas da UI do Grafana (fonte de edição)
│   ├── Hosts/
│   │   ├── linux-hosts.json
│   │   └── windows-hosts.json
│   └── Hosts + Database/
│       ├── linux-mysql-hosts.json
│       ├── linux-pgsql-hosts.json
│       └── windows-mssql-hosts.json
│
└── grafana/provisioning/dashboards/    # ← Formato de provisioning (carregado automaticamente)
    ├── Hosts/
    │   ├── linux-hosts.json
    │   └── windows-hosts.json
    └── Hosts + Database/
        ├── linux-mysql-hosts.json
        ├── linux-pgsql-hosts.json
        └── windows-hosts-mssql.json
```

> **Regra de ouro:** Nunca edite diretamente os arquivos de `grafana/provisioning/dashboards/`. Edite no Grafana, exporte o JSON para `grafana-dashboards-backup/`, converta para o formato de provisioning e faça commit.

---

## Fluxo de Trabalho

```
[Edição no Grafana UI]
        │
        ▼
[Dashboard → Share → Export JSON]
        │
        ▼
[Salvar em grafana-dashboards-backup/ ]
        │
        ▼
[Converter para formato de provisioning]  ← Este documento explica este passo
        │
        ▼
[Copiar para grafana/provisioning/dashboards/]
        │
        ▼
[git commit + git push]
        │
        ▼
[Grafana carrega automaticamente no próximo restart]
```

---

## Conversão: Export do Grafana 13 → Formato de Provisioning

### O Problema

O Grafana 13 introduziu um novo schema de dashboard (`dashboard.grafana.app/v2`) que é **incompatível** com o formato de provisioning anterior. Um dashboard exportado da UI do Grafana 13 **não pode ser carregado diretamente** via provisioning — é necessária uma transformação.

### Diferença entre os Formatos

**Formato exportado pela UI (backup) — NÃO funciona diretamente no provisioning:**
```json
{
  "annotations": [...],
  "cursorSync": "Off",
  "editable": true,
  "elements": {...},
  "layout": {...},
  "links": [...],
  "preload": false,
  "schemaVersion": 41,
  "tags": [...],
  "templating": {...},
  "timepicker": {...},
  "timezone": "browser",
  "title": "Linux + MySQL Hosts"
}
```
> ⚠️ **Observação:** O arquivo exportado **não possui campo `uid`**. O Grafana 13 remove o `uid` na exportação para evitar conflitos.

**Formato de provisioning — O que o Grafana carrega automaticamente:**
```json
{
  "apiVersion": "dashboard.grafana.app/v2",
  "kind": "Dashboard",
  "metadata": {
    "name": "linux-mysql-hosts"
  },
  "spec": {
    "annotations": [...],
    "cursorSync": "Off",
    "editable": true,
    "elements": {...},
    "layout": {...},
    "links": [...],
    "preload": false,
    "schemaVersion": 41,
    "tags": [...],
    "templating": {...},
    "timepicker": {...},
    "timezone": "browser",
    "title": "Linux + MySQL Hosts",
    "uid": "linux-mysql-hosts"
  }
}
```

### O que muda — Checklist de Conversão

| # | O que fazer | Detalhe |
|---|---|---|
| 1 | **Adicionar envelope externo** | Envolver todo o conteúdo com `apiVersion`, `kind`, `metadata` e mover tudo para dentro de `spec: {}` |
| 2 | **Definir `metadata.name`** | Usar o UID canônico do dashboard (ex: `linux-mysql-hosts`). Deve ser único na instância Grafana |
| 3 | **Adicionar campo `uid` dentro de `spec`** | O mesmo valor de `metadata.name`. Garante que o Grafana não recrie o dashboard com ID aleatório |
| 4 | **Remover `uid` do arquivo de backup** | O arquivo `grafana-dashboards-backup/` não deve ter `uid` para evitar conflitos ao importar manualmente pela UI |

### Script de Conversão (Python)

Salve como `tools/convert-dashboard.py` ou execute diretamente:

```python
#!/usr/bin/env python3
"""
Converte um dashboard exportado do Grafana 13 para o formato de provisioning.

Uso:
    python3 convert-dashboard.py <backup.json> <output-provisioning.json> <uid>

Exemplo:
    python3 convert-dashboard.py \
        "grafana-dashboards-backup/Hosts + Database/linux-mysql-hosts.json" \
        "grafana/provisioning/dashboards/Hosts + Database/linux-mysql-hosts.json" \
        "linux-mysql-hosts"
"""
import json, sys

def convert(backup_path, output_path, uid):
    with open(backup_path, 'r') as f:
        content = json.load(f)

    # Garante que uid está presente no spec
    content['uid'] = uid

    # Cria o envelope de provisioning
    provisioning = {
        "apiVersion": "dashboard.grafana.app/v2",
        "kind": "Dashboard",
        "metadata": {
            "name": uid
        },
        "spec": content
    }

    with open(output_path, 'w') as f:
        json.dump(provisioning, f, indent=2, ensure_ascii=False)

    print(f"✅ Gerado: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: convert-dashboard.py <backup.json> <output.json> <uid>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
```

---

## UIDs Canônicos dos Dashboards

> ⚠️ **Nunca altere os UIDs** de dashboards já em produção. Isso quebra bookmarks, links e alertas configurados.

| Dashboard | UID | metadata.name |
|---|---|---|
| Linux Hosts | `linux-hosts` | `linux-hosts` |
| Windows Hosts | `windows-hosts` | `windows-hosts` |
| Linux + MySQL Hosts | `linux-mysql-hosts` | `linux-mysql-hosts` |
| Linux + PostgreSQL Hosts | `linux-pgsql-hosts` | `linux-pgsql-hosts` |
| Windows + MSSQL Hosts | `windows-hosts-mssql` | `windows-hosts-mssql` |

---

## Como o Provisioning Funciona

O Grafana lê os arquivos de `grafana/provisioning/dashboards/` na inicialização através do arquivo de configuração `grafana/provisioning/dashboards/dashboards.yaml`:

```yaml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: true
```

- **`foldersFromFilesStructure: true`** → As subpastas (`Hosts/`, `Hosts + Database/`) viram pastas no Grafana automaticamente.
- **`updateIntervalSeconds: 10`** → O Grafana verifica mudanças nos arquivos a cada 10 segundos (hot-reload sem restart).
- **`allowUiUpdates: true`** → Permite edição pela UI, mas as mudanças são perdidas no próximo reload se não fizer o export/backup.

---

## Erros Comuns

### Dashboard não aparece após restart

**Causa:** Arquivo de provisioning sem o envelope `apiVersion/kind/metadata/spec`.

**Solução:** Execute a conversão descrita acima.

### Dashboard duplicado (dois cards na UI)

**Causa:** O arquivo de provisioning tem `uid` diferente do que está salvo no banco de dados do Grafana.

**Solução:** Delete o dashboard duplicado pela UI e reinicie o Grafana para o provisioning recriar com o UID correto.

### Edições perdidas após reiniciar

**Causa:** `allowUiUpdates: true` permite editar na UI, mas o arquivo de provisioning não foi atualizado.

**Solução:** Sempre que fizer mudanças significativas, exporte o dashboard pela UI, aplique a conversão e faça commit.

### Erro "invalid dashboard schema"

**Causa:** O Grafana 13 rejeita dashboards com `schemaVersion` antigo ou campos inválidos.

**Solução:** Exporte o dashboard de uma instância Grafana 13 atualizada para garantir o schema correto.

---

🔙 Voltar: [README Principal](README.md)
