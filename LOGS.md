# Logs (Loki, Alloy Syslog e OTLP)

Este documento cobre somente a política de logs da stack.

As entradas de log são:

1. Logs de aplicações via OTLP no Alloy Gateway.
2. Logs locais do host e dos containers via Alloy Agent.

## Categorias

Cada log recebe um label `category` que classifica sua origem:

| Category | Serviços |
|---|---|
| `security` | ssh |
| `system` | kernel |
| `application` | container-engine, containerd, cron |
| `platform` | systemd |

## Coleta do host

O agent não lê o journald inteiro. Cada serviço monitorado tem seu próprio arquivo em `alloy-agent/conf.d/` e seu próprio pipeline isolado.

Os arquivos seguem a convenção `<número>-log-<category>-<serviço>.alloy`:

| Arquivo | Category | Serviço | Drop |
|---|---|---|---|
| `200-log-sec-ssh.alloy` | `security` | ssh | — |
| `225-log-sys-kernel.alloy` | `system` | kernel | priority 5\|6\|7 |
| `250-log-app-docker.alloy` | `application` | container-engine | priority 6\|7 |
| `251-log-app-containerd.alloy` | `application` | containerd | priority 6\|7 |
| `252-log-app-cron.alloy` | `application` | cron | priority 6\|7 |
| `275-log-plt-systemd.alloy` | `platform` | systemd | priority 5\|6\|7 |

Cada arquivo segue o padrão de 4 componentes encadeados via `forward_to`:

| Passo | Componente | Responsabilidade |
|---|---|---|
| SOURCE | `loki.source.journal` | coleta do journal filtrado por `_SYSTEMD_UNIT`; expõe campos `__journal_*` via `relabel_rules` |
| TRANSFORM | `loki.relabel` | opera em labels (`priority` numérico → `level` textual, labels de ambiente) |
| NORMALIZE | `loki.process` | opera no conteúdo do log (entry): drop por priority, labels estáticos finais |
| WRITE | `loki.write` | envia para o alloy-gateway |

A convenção de nomes dos componentes é `<serviço>_<passo>`, ex: `ssh_transform`, `ssh_normalize`, `ssh_gateway`.

## Labels padrão

Todos os logs do host incluem os seguintes labels:

| Label | Origem | Exemplo |
|---|---|---|
| `category` | estático no pipeline | `security`, `system`, `application`, `platform` |
| `service_name` | estático no pipeline | `ssh`, `kernel`, `container-engine` |
| `level` | mapeado de `PRIORITY` do journal | `info`, `warning`, `error` |
| `instance` | `HOSTNAME` env | `code` |
| `environment` | `ENVIRONMENT` env | `prd` |
| `cloud_provider` | `CLOUD_PROVIDER` env | `mgc` |
| `cloud_region` | `CLOUD_REGION` env | `br-se1` |
| `cloud_availability_zone` | `CLOUD_AVAILABILITY_ZONE` env | `a` |

## Retenção

Definido organicamente na chave `.env` global pela cláusula `LOKI_RETENTION`.
*   Valor Padrão Original: **`30d`**
*   Após a expiração, os _chunks_ são apagados assincronamente da pasta interna `/lgtm/loki`.

> **Requisito técnico:** quando `retention_enabled: true`, o Loki exige `delete_request_store: filesystem` no bloco `compactor` do `loki.yaml`.
> ```
> CONFIG ERROR: compactor.delete-request-store should be configured when retention is enabled
> ```
> O `loki.yaml` desta stack já inclui essa configuração.

## Estimativa de armazenamento

A compressão típica que você experimentará será em torno de `10:1` (Sua aplicação gera 100GB de texto bruto HTTP 200/500, e o Loki formata isso comprimido usando apenas 10GB de seu HD). Isso sem contar o *Overhead* residual do Índice (WAL de 30% a 50%).

Cálculo prático de longo prazo:
`Disco Usado (GB) = [Sua App cospindo em GB/dia] × 0.1 × [Dias na var LOKI_RETENTION] × 1.5`

Para topologia de ingestão e papel do Gateway, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](README.md)
