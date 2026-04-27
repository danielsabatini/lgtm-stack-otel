# Guia de Alertas: Como Criar e o que Monitorar (Baseline)

Este documento unifica o **conhecimento técnico** de como configurar alertas no Grafana 13 com a **estratégia de monitoração** mínima necessária para a LGTM Stack.

---

## 1. Como Criar Alertas no Grafana 13

O sistema utiliza o **Unified Alerting**. O fluxo de trabalho é:

### Passo 1: Configurar o Ponto de Contato (Contact Point)
Antes de criar a lógica, defina para onde o alerta vai:
1.  Acesse **Alerting > Contact points**.
2.  Clique em **+ Add contact point**.
3.  Escolha o tipo (ex: `Slack`, `Discord`, `Email`).
4.  Insira a URL do Webhook ou as credenciais necessárias.
5.  **Teste o disparo** e salve.

### Passo 2: Criar a Regra de Alerta (Alert Rule)
1.  Acesse **Alerting > Alert rules > + Create alert rule**.
2.  **Nome:** Use um padrão claro (ex: `[INFRA] Host Offline`).
3.  **Query:** Insira a query PromQL (veja a lista abaixo).
4.  **Condição:** Defina o limite (ex: `IS BELOW 1` para disponibilidade).
5.  **Intervalo (For):** Use `2m` ou `5m` para evitar "flapping" (alertas que sobem e descem muito rápido).
6.  **Pastas:** Organize por tipo (Infra, Apps, DBs).

---

## 2. Alertas Mínimos Necessários (Baseline)

Abaixo estão os alertas fundamentais para garantir que você não seja pego de surpresa.

### A. Camada de Infraestrutura e Stack (LGTM-STACK)
Estes garantem que a própria monitoração e o host principal estejam saudáveis.

| Nome do Alerta | Query PromQL | Condição | Motivo |
| :--- | :--- | :--- | :--- |
| **Instância Offline** | `up == 0` | Por 2 min | O servidor ou o exportador parou. |
| **Disco Crítico** | `(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100` | `< 10` | Se o disco encher, o Loki/Mimir param de gravar. |
| **Memória Crítica** | `(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100` | `< 5` | Risco de OOM no sistema operacional. |
| **Container OOM Kill** | `increase(container_oom_events_total[5m])` | `> 0` | Um container da stack morreu por falta de RAM. |

### B. Camada Linux (Servidores Remotos)
| Nome do Alerta | Query PromQL | Condição | Motivo |
| :--- | :--- | :--- | :--- |
| **Filesystem / Full** | `node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes < 0.05` | `< 5%` | Previne falhas de boot/SO por disco cheio. |

### C. Camada Windows e MSSQL (Bancos de Dados)
| Nome do Alerta | Query PromQL | Condição | Motivo |
| :--- | :--- | :--- | :--- |
| **SQL Buffer Cache Hit** | `(windows_mssql_bufman_buffer_cache_hits / windows_mssql_bufman_buffer_cache_lookups) * 100` | `< 90` | O SQL está lendo muito do disco (lentidão). |
| **SQL Deadlocks** | `increase(windows_mssql_locks_deadlocks[5m])` | `> 0` | Transações estão sendo abortadas por conflito. |
| **SQL PLE Low** | `windows_mssql_bufman_page_life_expectancy_seconds` | `< 300` | Indica pressão severa de memória no banco. |

---

## 3. Melhores Práticas Operacionais

1.  **Use Severidades:**
    *   `Critical`: Dispara para celular/telefone (ex: Host Down).
    *   `Warning`: Dispara apenas para o chat/Slack (ex: Disco em 20%).
2.  **Group Wait:** Configure na **Notification Policy** um tempo de espera (ex: 30s) para que o Grafana agrupe múltiplos alertas da mesma instância em uma única mensagem.
3.  **Use o Grafana Assistant (IA):** Na dúvida sobre uma query, use o ícone de IA na criação do alerta e peça em português: *"Me mostre o uso de CPU desse container nos últimos 5 minutos"*.

## 4. Regra de Sincronização (Alert ↔ Threshold)

Para manter a stack **Lean** e evitar confusão operacional:
- **Exclusividade:** Thresholds visuais nos dashboards devem existir **apenas** para métricas que possuem alertas configurados.
- **Paridade:** O valor que dispara o alerta deve ser exatamente o mesmo valor onde a cor do gráfico muda para Vermelho (Critical) ou Amarelo (Warning).
- **Consistência:** Se o gráfico está vermelho, o alerta deve estar disparado.

---
🔙 Voltar: [README Principal](README.md)
