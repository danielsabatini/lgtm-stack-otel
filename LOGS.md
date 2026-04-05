# Logs (Loki, Alloy Syslog e OTLP)

O Loki não indexa logs por completo. Ele indexa **Metadata / Labels**, o que faz dele baratíssimo para se manter em infraestruturas enxutas. 

Nossa coleta de logs se divide de duas formas neste repositório:
1. Logs do Código (Seu Software) via OTLP direto para o Gateway.
2. Logs do Sistema / Daemons Internos gerados invisivelmente nos arquivos e syslogs da instância.

## Política de Coleta (Lean Syslog)

Num ecossistema saudável, não temos por que varrer os logs sistêmicos do Kernel Linux. Registros de `CRON`, pam_unix (ssh), network dispatchers causam apenas ruído visual na aba "Explore" do Grafana e geram GBs de índice inúteis.

*   **Implementação Anti-Ruído:** Dentro do nosso `alloy-agent`, blindamos o `loki.source.journal "system"`. 
*   Em vez de ler do `/var/log` de forma genérica, injetamos `matches = "_SYSTEMD_UNIT=docker.service"`.

**O Resultado:** Do host, o Loki indexará e engolirá apenas catástrofes e reboots inesperados ocorridos do Motor Docker em si. O ruído do S.O foi suprimido 100%. Seus dashboards exibirão majoritariamente _apenas ocorrências que o seu software ou seus devs registraram_.

## Política de Retenção

Definido organicamente na chave `.env` global pela cláusula `LOKI_RETENTION`.
*   Valor Padrão Original: **`30d`**
*   Após a expiração, os _chunks_ são apagados assincronamente da pasta interna `/lgtm/loki`.

> **Requisito Técnico — `delete_request_store`:** Quando `retention_enabled: true`, o Loki exige obrigatoriamente a chave `delete_request_store: filesystem` no bloco `compactor` do `loki.yaml`. Sem ela, o boot falha com:
> ```
> CONFIG ERROR: compactor.delete-request-store should be configured when retention is enabled
> ```
> O `loki.yaml` desta stack já inclui essa configuração.

## Estimativa de Armazenamento e Performance

A compressão típica que você experimentará será em torno de `10:1` (Sua aplicação gera 100GB de texto bruto HTTP 200/500, e o Loki formata isso comprimido usando apenas 10GB de seu HD). Isso sem contar o *Overhead* residual do Índice (WAL de 30% a 50%).

Cálculo prático de longo prazo:
`Disco Usado (GB) = [Sua App cospindo em GB/dia] × 0.1 × [Dias na var LOKI_RETENTION] × 1.5`

A arquitetura também obriga os chunks vindos de OTLP a adentrarem primeiro no *Processor Batch* do Alloy Gateway. Assim, milhares de _log lines_ geradas sequencialmente na mesma fração de segundo são empacotadas em um único envelope ZIP pesado e cadenciado antes de bater nas rotinas gRPC da porta interna do container do banco, poupando CPU.

---
🔙 Voltar: [README Principal](README.md)
