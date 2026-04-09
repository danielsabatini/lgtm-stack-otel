# Logs (Loki, Alloy Syslog e OTLP)

Este documento cobre somente a política de logs da stack.

As entradas de log são:

1. Logs de aplicações via OTLP no Alloy Gateway.
2. Logs locais do host e dos containers via Alloy Agent.

## Coleta do host

O agent não lê o journald inteiro.

- Cada serviço do systemd monitorado possui sua própria instância de `loki.source.journal`.
- Hoje a coleta local cobre `docker.service` e `sshd.service`.
- Todos esses fluxos convergem para o mesmo `loki.relabel`.

Se a topologia do agent mudar, a fonte da verdade é `alloy-agent/config.alloy`.

## Logs de containers

O agent coleta `stdout` e `stderr` dos containers via Docker API.

- O nome do container é mapeado para `service_name`.
- O mesmo nome também é copiado para `name` para compatibilidade com os dashboards provisionados.
- O campo `level` é extraído do conteúdo do log e salvo como structured metadata do Loki.
- O drop de `debug` e `trace` permanece opcional e comentado no `config.alloy`.

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
