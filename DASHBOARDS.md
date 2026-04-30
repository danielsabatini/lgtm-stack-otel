# Dashboards Grafana

Referência dos templates de dashboard disponíveis na stack.

## Estrutura de Dashboards

Todos os dashboards são provisionados automaticamente pelo Grafana no inicialização via provisioning automation. O diretório `grafana-dashboards-backup/` armazena backups em formato JSON dos dashboards editados via UI.

## Hosts + Database

Templates pré-configurados para monitoramento de hosts com banco de dados utilizando o framework dos 6+2 Pilares.

| Dashboard | Caminho | Tipo de Coleta | Descrição |
|-----------|---------|----------------|-----------|
| **Linux + PostgreSQL** | `grafana-dashboards-backup/Hosts + Database/linux-pgsql-hosts.json` | Pull via Alloy Gateway | Coleta de métricas do sistema operacional (node_exporter) e PostgreSQL (postgres_exporter) em um único dashboard. Recomendado para ambientes legados sem Alloy Agent. |
| **Linux + MySQL** | `grafana-dashboards-backup/Hosts + Database/linux-mysql-hosts.json` | Pull via Alloy Gateway | Coleta de métricas do sistema operacional (node_exporter) e MySQL InnoDB (mysqld_exporter) em um único dashboard. Recomendado para ambientes legados sem Alloy Agent. |

### Como usar

1. Acesse Grafana em `http://localhost:3000` (usuário padrão: `admin`)
2. Navegue até a seção de Dashboards
3. Procure por "Linux + PostgreSQL" ou "Linux + MySQL"
4. Use a variável `$instance` no seletor de host para filtrar dados

### Variáveis do Dashboard

- `instance` (obrigatório): Nome do host monitorado (ex: `srv-pgsql-01`, `srv-mysql-01`)
- Compatível com labels definidos na configuração de coleta via `prometheus.relabel`

### Pilares Cobertos

Ambos os dashboards cobrem os 6+2 Pilares do framework:

1. **HEALTH** — Status up/down, conexões ativas, latência média de queries
2. **CAPACITY** — CPU, Memória, Disco, Buffers e cache do banco
3. **ACTIVITY** — Throughput de queries, rows processadas, I/O
4. **DIAGNOSTICS** — Locks, deadlocks, contentions, bloqueios
5. **INVENTORY** — Informações de OS (kernel, arquitectura, distribuição)
6. **LOGS** — Compatível com ingestão de logs via Loki (configuração separada)
7. **METRICS** (opcional) — Métricas específicas do banco (WAL, redo logs, binlog)

### Mapeamento de Métricas

Ambos os dashboards utilizam métricas equivalentes entre PostgreSQL e MySQL conforme documentado nos respectivos templates (`pull-linux-dbaas-pgsql-hosts.alloy` e `pull-linux-dbaas-mysql-hosts.alloy`).

---

## Workflow de Edição

> [!IMPORTANT]
> **Não edite os arquivos `.json` diretamente no disco durante sessão de edição no Grafana.**

1. **Editar no Grafana UI** (ou via API)
2. **Salvar e publicar** no Grafana
3. **Fazer backup** via UI (menu do dashboard → Download JSON)
4. **Copiar para disco** em `grafana-dashboards-backup/Hosts + Database/`
5. **Fazer commit** no git

Isso garante que:
- As mudanças sejam persistidas (backup)
- O arquivo em disco represente o estado atual do dashboard
- Seja possível restaurar em caso de problemas

---

🔙 Voltar: [README Principal](README.md)
