# Logs (Loki, Alloy Syslog e OTLP)

> **Referência Técnica:** Este documento estabelece a política de categorização, labels, pipelines de coleta e retenção de logs no Grafana Loki.

---

## 1. Introdução

A agregação de logs na LGTM Stack é desenhada para oferecer busca em tempo real com baixo consumo de armazenamento. Em vez de indexar o texto completo de cada linha (o que geraria índices gigantescos e lentidão), o Grafana Loki indexa apenas os **metadados (labels)** e compacta o conteúdo das mensagens em blocos (*chunks*).

Para evitar que o Loki se torne um repositório confuso de mensagens desordenadas, todos os logs coletados são enriquecidos com uma categoria funcional padronizada.

---

## 2. Objetivo

1. **Estruturar os Logs por Categoria:** Garantir que todos os logs pertençam a uma das 4 categorias canônicas de observabilidade.
2. **Definir Padrão de Labels:** Padronizar as tags de identificação de instâncias, serviços e severidade.
3. **Controlar o Descarte de Ruído:** Filtrar na origem logs rotineiros desnecessários para economizar até 80% de armazenamento.

---

## 3. Endpoints e Roteamento de Ingestão

Toda a ingestão de logs é centralizada no **Alloy Gateway**:
* **Porta 9998:** Recepção de streams via API de Push nativa do Loki (usada pelos Alloy Agents nos hosts).
* **Portas 4317 / 4318:** Recepção de logs estruturados de aplicações no padrão OpenTelemetry (OTLP).

---

## 4. As 4 Categorias Padronizadas de Logs

Conforme definido na metodologia de observabilidade ([OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md)), todos os logs recebem a label `category` para facilitar a filtragem nos dashboards:

| Categoria (`category`) | Contexto Operacional | O que Coleta |
|---|---|---|
| **`security`** | Autenticação e Auditoria | Acessos SSH, logins em painéis, bloqueios de firewall/ACL e comandos `sudo`. |
| **`system`** | Sistema Operacional e Kernel | Mensagens de boot, eventos do kernel (`dmesg`), intervenções do OOM Killer e erros de disco. |
| **`application`** | Aplicações e Runtimes | Logs de contêineres Docker/containerd, tarefas agendadas (`cron`), exceções e queries lentas. |
| **`platform`** | Gerenciador de Serviços | Inicialização, paradas inesperadas e ciclo de vida de daemons no `systemd` e Windows SCM. |

---

## 5. Pipelines de Coleta no Host Linux (Alloy Agent)

O Alloy Agent não lê o journald de forma cega. Cada serviço monitorado possui um arquivo de pipeline isolado em `alloy-agent/conf.d/` seguindo a convenção `<número>-log-<categoria>-<serviço>.alloy`:

| Arquivo | Categoria | Serviço | Filtro de Descarte (Otimização) |
|---|---|---|---|
| `200-log-sec-ssh.alloy` | `security` | `ssh` | Mantém todos os eventos de acesso. |
| `225-log-sys-kernel.alloy` | `system` | `kernel` | Descarta mensagens informativas (prioridade 5, 6, 7). |
| `250-log-app-docker.alloy` | `application` | `container-engine` | Descarta debug e info rotineiro. |
| `251-log-app-containerd.alloy` | `application` | `containerd` | Descarta mensagens de nível baixo. |
| `252-log-app-cron.alloy` | `application` | `cron` | Filtra execuções rotineiras sem erro. |
| `275-log-plt-systemd.alloy` | `platform` | `systemd` | Mantém apenas avisos e falhas de serviços. |

### Fluxo em 4 Etapas de Cada Pipeline:
1. **SOURCE (`loki.source.journal`):** Coleta filtrada pela unit do systemd.
2. **TRANSFORM (`loki.relabel`):** Converte a prioridade numérica em texto (`info`, `warning`, `error`).
3. **NORMALIZE (`loki.process`):** Aplica regras de descarte de ruído e formata a mensagem.
4. **WRITE (`loki.write`):** Envia o stream de log compactado para o Alloy Gateway.

---

## 6. Coleta no Windows (Windows Event Log)

No Windows, o agente lê diretamente da API nativa do **Windows Event Log**:

| Categoria | Canal do Event Log | O que Coleta |
|---|---|---|
| `security` | `Security` | Eventos de logon (4624/4625), privilégios e auditoria de contas. |
| `system` | `System` | Erros de hardware, drivers e falhas do sistema operacional. |
| `application` | `TaskScheduler/Operational` | Falhas no Agendador de Tarefas do Windows. |
| `platform` | `System` (Provider: SCM) | Falhas de inicialização e paradas de serviços do Windows. |
| `database` | `Application` (Provider: MSSQL) | Erros transacionais e alertas do SQL Server (Severity ≥ 17). |

---

## 7. Esquema Global de Labels

Todos os streams de log carregam os labels de identidade padronizados:

| Label | Descrição | Exemplo |
|---|---|---|
| `category` | Categoria funcional do log | `security`, `system`, `application`, `platform` |
| `service_name` | Nome do serviço de origem | `ssh`, `kernel`, `coredns`, `container-engine` |
| `level` | Nível de severidade da mensagem | `info`, `warning`, `error` |
| `instance` | Identificador único do host | `dns-ne1-1`, `db-prod-01` |
| `environment` | Ambiente de implantação | `prd`, `stg`, `dev` |
| `cloud_provider` | Provedor de nuvem | `mgc`, `aws`, `local` |
| `cloud_region` | Região geográfica | `br-se1`, `br-ne1` |

---

## 8. Retenção e Armazenamento

A retenção é controlada pela variável `LOKI_RETENTION` no arquivo `.env` (padrão: `30d`). A limpeza de chunks antigos ocorre automaticamente pelo componente *compactor* do Loki.

Para cálculos de impacto em disco e dimensionamento, consulte [SIZING.md](SIZING.md).

---

## 9. Governança e Referências

* Para a metodologia completa de observabilidade e correlação com métricas/traces, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para a topologia de rede e isolamento do Gateway, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](../README.md)
